# Qdrant Benchmark — Full Architecture

## 1. Project Overview

A distributed benchmarking platform for measuring **Qdrant** (open-source vector database) performance across various search scenarios. The system uses a two-node topology connected over a 10 Gbps link:

| Node | Role | Key Component |
|------|------|---------------|
| **Node 1** (Bench Client) | Generates load & collects results | VectorDBBench (Python) |
| **Node 2** (Qdrant Server) | Serves vector search queries | Qdrant v1.17.0 (Rust) |

---

## 2. Directory Structure

```
qdrant-benchmark/
├── .claude/
│   └── settings.local.json            # Claude Code permission config
│
├── bench-client/                       # ── VectorDBBench Client ──
│   ├── Dockerfile                      # Python 3.11-slim + vectordb-bench[qdrant]
│   ├── docker-compose.yaml             # Client service definition
│   ├── config/                         # Runtime configuration (mounted volume)
│   └── results/                        # Benchmark output (mounted volume)
│
├── qdrant-server/                      # ── Qdrant Server (alt layout) ──
│   └── qdrant_storage/                 # Symlink to primary storage
│
├── qdrant_storage/                     # ── Primary Persistent Storage ──
│   ├── aliases/
│   │   └── data.json                   # Collection alias mappings
│   ├── collections/                    # Vector collection data (HNSW indices)
│   └── raft_state.json                 # Raft consensus state (single-node)
│
├── docker-compose.yaml                 # Root Qdrant service (official image)
├── Dockerfile.qdrant                   # Custom Qdrant build from source
├── build_qdrant_server.sh              # Docker build wrapper script
├── run_qdrant_server.sh                # Docker run wrapper script
├── PLAN.md                             # Step-by-step execution guide
└── FULL_ARCHITECTURE.md                # This file
```

---

## 3. Component Details

### 3.1 Qdrant Server

**Two deployment options:**

#### Option A — Official Image (docker-compose.yaml)

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports: 6333 (REST), 6334 (gRPC)
    volumes: ./qdrant_storage:/qdrant/storage
    mem_limit: 32g
    restart: always
```

#### Option B — Custom Build (Dockerfile.qdrant)

- Multi-stage build: `rust:latest` → `debian:bookworm-slim`
- Pinned version: **v1.17.0**
- Jemalloc with **64KB page size** (`LG_PAGE=16`) for ARM64/large-page systems
- Build deps: cmake, g++, clang, protobuf-compiler, libunwind-dev
- Built via `build_qdrant_server.sh` → image tagged `qdrant-64k:v1.17.0`
- Run via `run_qdrant_server.sh` with volume mount and port mapping

**Exposed Interfaces:**

| Port | Protocol | Purpose |
|------|----------|---------|
| 6333 | HTTP REST | Collection/point CRUD, search, telemetry |
| 6334 | gRPC | Low-latency vector operations |

**Key REST Endpoints:**

| Endpoint | Description |
|----------|-------------|
| `GET /healthz` | Health check |
| `GET /telemetry` | Performance metrics & resource usage |
| `GET /collections` | List all collections |
| `POST /collections/{name}/points/search` | Vector similarity search |

### 3.2 VectorDBBench Client

**Image:** `python:3.11-slim` with `vectordb-bench[qdrant]` pip package

**Entrypoint:** `sleep infinity` — container stays alive for manual/scripted test invocations via `docker exec`.

**CLI Interface:**
```bash
vectordbbench QdrantLocal \
  --url http://<NODE2_IP>:6333 \
  --case-type <CaseType> \
  --m <hnsw_m> --ef-construct <val> --hnsw-ef <val> \
  --num-concurrency 1,10,50,100 \
  --db-label "<label>"
```

**Volume Mounts:**

| Host Path | Container Path | Purpose |
|-----------|----------------|---------|
| `./results` | `/bench/results` | Benchmark output files |
| `./config` | `/bench/config` | Client configuration |

---

## 4. Data Flow

```
                       10 Gbps Network
                    ┌──────────────────┐
                    │                  │
  ┌─────────────┐   │   ┌──────────────┐
  │  Node 1     │   │   │  Node 2      │
  │             │   │   │              │
  │ VectorDB    │───┼──▶│  Qdrant      │
  │  Bench      │   │   │  Server      │
  │             │◀──┼───│              │
  │  /results/  │   │   │  /storage/   │
  └─────────────┘   │   └──────────────┘
                    │                  │
                    └──────────────────┘
```

**Execution sequence:**

1. **Qdrant starts** → initializes storage, Raft state, opens ports 6333/6334
2. **Client starts** → container idles, awaiting `docker exec` commands
3. **Ingestion** → client loads dataset vectors, sends to Qdrant via REST/gRPC
4. **Indexing** → Qdrant builds HNSW index (parameterized by `m`, `ef-construct`)
5. **Search** → client issues concurrent queries, measures latency/throughput/recall
6. **Results** → metrics written to `/bench/results/`, archived as `tar.gz`

---

## 5. Benchmark Test Matrix

### 6 Rounds (~3–4 hours total)

| Round | Case Type | Vectors | Dimensions | Duration | Purpose |
|-------|-----------|---------|------------|----------|---------|
| 1 | `Performance1536D50K` | 50K | 1536 | ~5 min | Smoke test |
| 2 | `Performance768D1M` | 1M | 768 | ~15 min | Baseline performance |
| 3 | `Performance1536D500K` | 500K | 1536 | ~15 min | High-dimensional |
| 4a | `Filtering768D1M1P` | 1M | 768 | ~20 min | 1% filter selectivity |
| 4b | `Filtering768D1M99P` | 1M | 768 | (included) | 99% filter selectivity |
| 5 | `Performance768D10M` | 10M | 768 | 1–2 hrs | Scale test |
| 6 | `CapacityDim128` | varies | 128 | ~30 min | Capacity limits |

### HNSW Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `m` | 16 | Max connections per graph node |
| `ef-construct` | 200 | Index build-time search width |
| `hnsw-ef` | 128 | Query-time search width |

### Concurrency Levels

Tests run at **1, 10, 50, 100** concurrent requests to measure throughput scaling and latency degradation.

---

## 6. Storage Architecture

### Qdrant Persistent Storage (`qdrant_storage/`)

```
qdrant_storage/
├── aliases/data.json       # {} — collection name aliases
├── collections/            # Per-collection directories (HNSW indices + vectors)
└── raft_state.json         # Single-node Raft state
```

**Raft State** (single-node cluster):
- Peer ID: `7820436048423567`
- Term/Vote/Commit: all `0` (fresh initialization)

**Storage is mounted** from host into the Docker container at `/qdrant/storage`, ensuring data persists across container restarts.

---

## 7. Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Vector DB | **Qdrant v1.17.0** | Rust, HNSW indexing |
| Memory Allocator | **jemalloc** | 64KB page size for ARM64/large-page |
| Benchmark Framework | **VectorDBBench** | Python, supports multiple DBs |
| Qdrant Client | **qdrant-client** (Python) | REST + gRPC support |
| Containerization | **Docker + Compose** | Isolated, reproducible |
| Consensus | **Raft** | Single-node (expandable to cluster) |
| Index Algorithm | **HNSW** | Hierarchical Navigable Small World |

---

## 8. Hardware Requirements

| Resource | Node 1 (Client) | Node 2 (Server) |
|----------|-----------------|-----------------|
| CPU | 4+ cores | 8+ cores |
| RAM | 8 GB+ | 32 GB (Docker limit) |
| Storage | Minimal | 100 GB+ SSD |
| Network | 10 Gbps | 10 Gbps |
| File descriptors | Default | 65536 (ulimit) |

---

## 9. Monitoring & Observability

```bash
# Container resource usage (CPU, memory, network I/O)
docker stats qdrant-server

# Qdrant telemetry (search metrics, indexing stats)
watch -n 5 'curl -s http://localhost:6333/telemetry | python3 -m json.tool | head -50'

# Health check
curl http://localhost:6333/healthz

# Network throughput validation
iperf3 -c <NODE2_IP> -t 10
```

---

## 10. Results Collection

```bash
# View results on client node
ls ~/qdrant-benchmark/bench-client/results/

# Package for export
tar czf qdrant-benchmark-results.tar.gz \
  -C ~/qdrant-benchmark/bench-client results/
```

Output includes: **throughput (QPS), latency (p50/p95/p99), recall**, organized by case type, concurrency level, and HNSW parameters.

---

## 11. Key Design Decisions

1. **Two-node separation** — isolates client load generation from server, preventing resource contention and producing realistic network-bound measurements.
2. **Custom jemalloc 64KB pages** — optimized for ARM64 or systems with non-standard page sizes; avoids memory fragmentation under heavy allocation.
3. **Pinned Qdrant v1.17.0** — ensures reproducible benchmarks across runs.
4. **`sleep infinity` entrypoint** — allows flexible, manual test orchestration rather than a single automated run.
5. **Volume-mounted storage** — data persists across container lifecycle; enables incremental testing without re-ingestion.
6. **32 GB memory limit** — constrains Qdrant to a known resource envelope, making results comparable across environments.
