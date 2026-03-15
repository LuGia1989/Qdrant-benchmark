"""
Qdrant hnsw_ef sweep: Load data once, then benchmark QPS & Recall
at different ef values to produce a Pareto curve.

Usage:
  docker exec vdbbench python3 /bench/sweep_ef.py \
      --url http://10.80.120.102:6333 \
      --dataset 1536d500k \
      --ef-values 16,32,64,128,256,512 \
      --concurrency 1,10,50,100 \
      --m 16 --ef-construct 200
"""

import argparse
import json
import multiprocessing as mp
import os
import time
from functools import partial

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Batch,
    CollectionStatus,
    HnswConfigDiff,
    OptimizersConfigDiff,
    PayloadSchemaType,
    SearchParams,
    VectorParams,
)

BATCH_SIZE = 500
COLLECTION_NAME = "ef_sweep_collection"
K = 100
CONCURRENT_DURATION = 30  # seconds per concurrency level


# ── Dataset helpers ──────────────────────────────────────────────

DATASET_MAP = {
    "1536d50k":  ("openai", "openai_small_50k",   50_000,  1536),
    "1536d500k": ("openai", "openai_medium_500k", 500_000,  1536),
    "1536d5m":   ("openai", "openai_large_5m",  5_000_000,  1536),
    "768d1m":    ("cohere", "cohere_medium_1m",  1_000_000,   768),
}


def prepare_dataset(dataset_key):
    """Download dataset if needed, return (train_path, test_path, gt_path, dim)."""
    from vectordb_bench.backend.dataset import Dataset
    from vectordb_bench.backend.data_source import DatasetSource

    ds_name, dir_name, size, dim = DATASET_MAP[dataset_key]
    ds_enum = Dataset[ds_name.upper()]
    dm = ds_enum.manager(size)
    dm.prepare(source=DatasetSource.S3)
    base = f"/tmp/vectordb_bench/dataset/{ds_name}/{dir_name}"
    return base, dim, dm


def load_test_data(base_path):
    """Load query vectors and ground truth from parquet files."""
    import pyarrow.parquet as pq

    test_table = pq.read_table(os.path.join(base_path, "test.parquet"))
    gt_table = pq.read_table(os.path.join(base_path, "neighbors.parquet"))

    test_embs = [row.as_py() for row in test_table.column("emb")]
    gt_ids = [row.as_py() for row in gt_table.column("neighbors_id")]

    return test_embs, gt_ids


def iter_train_batches(base_path, batch_size=BATCH_SIZE):
    """Yield (ids, embeddings) from training parquet in batches."""
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(os.path.join(base_path, "shuffle_train.parquet"))
    for batch in pf.iter_batches(batch_size=batch_size, columns=["id", "emb"]):
        ids = batch.column("id").to_pylist()
        embs = [e.as_py() for e in batch.column("emb")]
        yield ids, embs


# ── Qdrant operations ───────────────────────────────────────────

def create_collection(client, dim, m, ef_construct):
    """Create collection with HNSW index."""
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=dim, distance="Cosine"),
        hnsw_config=HnswConfigDiff(m=m, ef_construct=ef_construct),
    )
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="pk",
        field_schema=PayloadSchemaType.INTEGER,
    )
    print(f"  Created collection: dim={dim}, m={m}, ef_construct={ef_construct}")


def insert_data(client, base_path):
    """Insert all training vectors."""
    # disable indexing during insert
    client.update_collection(
        collection_name=COLLECTION_NAME,
        optimizer_config=OptimizersConfigDiff(indexing_threshold=0),
    )

    count = 0
    t0 = time.time()
    for ids, embs in iter_train_batches(base_path):
        payloads = [{"pk": i} for i in ids]
        client.upsert(
            collection_name=COLLECTION_NAME,
            wait=True,
            points=Batch(ids=ids, payloads=payloads, vectors=embs),
        )
        count += len(ids)
        if count % 50_000 == 0:
            elapsed = time.time() - t0
            print(f"  Inserted {count:,} vectors ({elapsed:.1f}s)")

    # re-enable indexing
    client.update_collection(
        collection_name=COLLECTION_NAME,
        optimizer_config=OptimizersConfigDiff(indexing_threshold=100),
    )
    elapsed = time.time() - t0
    print(f"  Insert complete: {count:,} vectors in {elapsed:.1f}s")
    return count, elapsed


def wait_for_index(client):
    """Wait until HNSW index is fully built."""
    print("  Waiting for index to build...", end="", flush=True)
    t0 = time.time()
    while True:
        info = client.get_collection(COLLECTION_NAME)
        if info.status == CollectionStatus.GREEN:
            elapsed = time.time() - t0
            print(f" done ({elapsed:.1f}s)")
            print(f"  Points: {info.points_count}, Indexed: {info.indexed_vectors_count}")
            return elapsed
        time.sleep(5)


# ── Search & metrics ─────────────────────────────────────────────

def search_single(client, query, ef, k=K):
    """Single search query, returns (result_ids, latency)."""
    t0 = time.time()
    res = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query,
        limit=k,
        search_params=SearchParams(exact=False, hnsw_ef=ef),
    )
    latency = time.time() - t0
    return [p.id for p in res.points], latency


def calc_recall(got, ground_truth, k=K):
    """Recall@k: fraction of true neighbors found."""
    gt_set = set(ground_truth[:k])
    found = sum(1 for r in got if r in gt_set)
    return found / k


def serial_search(client, test_embs, gt_ids, ef, k=K):
    """Run serial search over all queries, measure recall & latency."""
    latencies = []
    recalls = []

    for i, emb in enumerate(test_embs):
        result_ids, lat = search_single(client, emb, ef, k)
        latencies.append(lat)
        recalls.append(calc_recall(result_ids, gt_ids[i], k))

    latencies_ms = np.array(latencies) * 1000
    return {
        "recall": float(np.mean(recalls)),
        "qps_serial": 1.0 / float(np.mean(latencies)),
        "latency_avg_ms": float(np.mean(latencies_ms)),
        "latency_p95_ms": float(np.percentile(latencies_ms, 95)),
        "latency_p99_ms": float(np.percentile(latencies_ms, 99)),
        "num_queries": len(test_embs),
    }


def _concurrent_worker(args):
    """Worker for concurrent search. Runs queries for a fixed duration."""
    url, test_embs, ef, duration = args
    client = QdrantClient(url=url, prefer_grpc=True)
    rng = np.random.RandomState(os.getpid())
    n_queries = len(test_embs)

    count = 0
    latencies = []
    deadline = time.time() + duration

    while time.time() < deadline:
        idx = rng.randint(0, n_queries)
        _, lat = search_single(client, test_embs[idx], ef)
        latencies.append(lat)
        count += 1

    return count, latencies


def concurrent_search(url, test_embs, ef, concurrency_levels):
    """Run concurrent search at each concurrency level."""
    results = {}
    for conc in concurrency_levels:
        worker_args = [(url, test_embs, ef, CONCURRENT_DURATION)] * conc

        with mp.Pool(conc) as pool:
            worker_results = pool.map(_concurrent_worker, worker_args)

        total_queries = sum(r[0] for r in worker_results)
        all_latencies = []
        for r in worker_results:
            all_latencies.extend(r[1])

        lat_ms = np.array(all_latencies) * 1000
        qps = total_queries / CONCURRENT_DURATION

        results[conc] = {
            "qps": float(qps),
            "latency_avg_ms": float(np.mean(lat_ms)),
            "latency_p95_ms": float(np.percentile(lat_ms, 95)),
            "latency_p99_ms": float(np.percentile(lat_ms, 99)),
            "total_queries": total_queries,
        }
        print(f"    c={conc}: QPS={qps:.1f}, p99={np.percentile(lat_ms, 99):.1f}ms")

    return results


# ── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Qdrant hnsw_ef sweep benchmark")
    parser.add_argument("--url", required=True, help="Qdrant server URL")
    parser.add_argument("--dataset", default="1536d500k",
                        choices=list(DATASET_MAP.keys()),
                        help="Dataset to use")
    parser.add_argument("--ef-values", default="16,32,64,128,256,512",
                        help="Comma-separated hnsw_ef values to sweep")
    parser.add_argument("--concurrency", default="1,10,50,100",
                        help="Comma-separated concurrency levels")
    parser.add_argument("--m", type=int, default=16, help="HNSW m parameter")
    parser.add_argument("--ef-construct", type=int, default=200,
                        help="HNSW ef_construct parameter")
    parser.add_argument("--skip-load", action="store_true",
                        help="Skip data loading (reuse existing collection)")
    parser.add_argument("--output", default="/bench/results/ef_sweep_results.json",
                        help="Output JSON file path")
    args = parser.parse_args()

    ef_values = [int(x) for x in args.ef_values.split(",")]
    conc_levels = [int(x) for x in args.concurrency.split(",")]

    print(f"=== Qdrant ef Sweep Benchmark ===")
    print(f"Dataset: {args.dataset}")
    print(f"ef values: {ef_values}")
    print(f"Concurrency: {conc_levels}")
    print()

    # 1. Prepare dataset
    print("[1/4] Preparing dataset...")
    base_path, dim, dm = prepare_dataset(args.dataset)
    print(f"  Dataset ready at {base_path}")

    # 2. Load data (once)
    client = QdrantClient(url=args.url, prefer_grpc=True)
    if not args.skip_load:
        print("\n[2/4] Loading data into Qdrant...")
        create_collection(client, dim, args.m, args.ef_construct)
        insert_count, insert_duration = insert_data(client, base_path)
        optimize_duration = wait_for_index(client)
    else:
        print("\n[2/4] Skipping load (--skip-load)")
        insert_count = 0
        insert_duration = 0
        optimize_duration = 0

    # 3. Load test data
    print("\n[3/4] Loading test queries and ground truth...")
    test_embs, gt_ids = load_test_data(base_path)
    print(f"  {len(test_embs)} test queries, ground truth loaded")

    # 4. Sweep ef values
    print(f"\n[4/4] Sweeping {len(ef_values)} ef values...")
    all_results = {
        "dataset": args.dataset,
        "hnsw_m": args.m,
        "hnsw_ef_construct": args.ef_construct,
        "insert_count": insert_count,
        "insert_duration_s": insert_duration,
        "optimize_duration_s": optimize_duration,
        "k": K,
        "concurrent_duration_s": CONCURRENT_DURATION,
        "ef_sweep": [],
    }

    for ef in ef_values:
        print(f"\n  --- ef={ef} ---")

        # Serial search (recall + latency)
        print(f"  Serial search ({len(test_embs)} queries)...")
        serial = serial_search(client, test_embs, gt_ids, ef)
        print(f"    Recall@{K}: {serial['recall']:.4f}")
        print(f"    Serial QPS: {serial['qps_serial']:.1f}")
        print(f"    P99: {serial['latency_p99_ms']:.1f}ms")

        # Concurrent search (QPS)
        print(f"  Concurrent search...")
        conc = concurrent_search(args.url, test_embs, ef, conc_levels)

        ef_result = {
            "hnsw_ef": ef,
            "serial": serial,
            "concurrent": {str(k): v for k, v in conc.items()},
        }
        all_results["ef_sweep"].append(ef_result)

    # Save results
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to {args.output}")

    # Print summary table
    print("\n" + "=" * 80)
    print(f"{'ef':>6} | {'Recall':>8} | {'Serial QPS':>10} | ", end="")
    for c in conc_levels:
        print(f"{'QPS@c=' + str(c):>12} | ", end="")
    print(f"{'P99 (serial)':>12}")
    print("-" * 80)
    for r in all_results["ef_sweep"]:
        ef = r["hnsw_ef"]
        s = r["serial"]
        print(f"{ef:>6} | {s['recall']:>8.4f} | {s['qps_serial']:>10.1f} | ", end="")
        for c in conc_levels:
            qps = r["concurrent"].get(str(c), {}).get("qps", 0)
            print(f"{qps:>12.1f} | ", end="")
        print(f"{s['latency_p99_ms']:>10.1f}ms")
    print("=" * 80)


if __name__ == "__main__":
    main()
