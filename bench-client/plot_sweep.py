"""
Plot QPS vs Recall Pareto curve from ef sweep results.

Usage:
  docker exec vdbbench python3 /bench/plot_sweep.py \
      --input /bench/results/ef_sweep_results.json
"""

import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="/bench/results/ef_sweep_results.json")
    parser.add_argument("--output-dir", default="/bench/results/")
    args = parser.parse_args()

    with open(args.input) as f:
        data = json.load(f)

    sweep = data["ef_sweep"]
    dataset = data["dataset"]
    m = data["hnsw_m"]
    ef_construct = data["hnsw_ef_construct"]

    ef_values = [r["hnsw_ef"] for r in sweep]
    recalls = [r["serial"]["recall"] for r in sweep]
    serial_qps = [r["serial"]["qps_serial"] for r in sweep]
    serial_p99 = [r["serial"]["latency_p99_ms"] for r in sweep]

    # Get concurrency levels from first result
    conc_keys = sorted(sweep[0]["concurrent"].keys(), key=int)
    colors = ['#2196F3', '#FF5722', '#4CAF50', '#9C27B0', '#FF9800', '#795548']

    # ── Plot 1: QPS vs Recall (Pareto curve) ─────────────────────
    fig, ax = plt.subplots(figsize=(10, 7))

    # Serial
    ax.plot(recalls, serial_qps, 'o-', label='Serial (c=1)', color=colors[0],
            linewidth=2, markersize=8, zorder=5)
    for r, q, ef in zip(recalls, serial_qps, ef_values):
        ax.annotate(f'ef={ef}', (r, q), textcoords="offset points",
                    xytext=(8, 5), fontsize=8, color=colors[0])

    # Concurrent
    for i, ck in enumerate(conc_keys):
        conc_qps = [r["concurrent"][ck]["qps"] for r in sweep]
        ax.plot(recalls, conc_qps, 'o-', label=f'Concurrent (c={ck})',
                color=colors[(i + 1) % len(colors)], linewidth=2, markersize=8)
        for r, q, ef in zip(recalls, conc_qps, ef_values):
            ax.annotate(f'ef={ef}', (r, q), textcoords="offset points",
                        xytext=(8, 5), fontsize=7, alpha=0.7)

    ax.set_xlabel('Recall@100', fontsize=13)
    ax.set_ylabel('QPS', fontsize=13)
    ax.set_title(f'Qdrant: QPS vs Recall (dataset={dataset}, m={m}, ef_c={ef_construct})',
                 fontsize=14)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    path = os.path.join(args.output_dir, 'qps_vs_recall_pareto.png')
    plt.savefig(path, dpi=150)
    print(f"Saved {path}")

    # ── Plot 2: Latency vs Recall ────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 7))

    ax.plot(recalls, serial_p99, 'o-', label='Serial P99', color=colors[0],
            linewidth=2, markersize=8)
    for r, l, ef in zip(recalls, serial_p99, ef_values):
        ax.annotate(f'ef={ef}', (r, l), textcoords="offset points",
                    xytext=(8, 5), fontsize=8)

    for i, ck in enumerate(conc_keys):
        conc_p99 = [r["concurrent"][ck]["latency_p99_ms"] for r in sweep]
        ax.plot(recalls, conc_p99, 'o-', label=f'c={ck} P99',
                color=colors[(i + 1) % len(colors)], linewidth=2, markersize=8)

    ax.set_xlabel('Recall@100', fontsize=13)
    ax.set_ylabel('P99 Latency (ms)', fontsize=13)
    ax.set_title(f'Qdrant: Latency vs Recall (dataset={dataset}, m={m}, ef_c={ef_construct})',
                 fontsize=14)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    path = os.path.join(args.output_dir, 'latency_vs_recall.png')
    plt.savefig(path, dpi=150)
    print(f"Saved {path}")

    # ── Plot 3: ef value impact (multi-axis) ─────────────────────
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(16, 6))

    # Recall vs ef
    ax1.plot(ef_values, recalls, 'o-', color=colors[0], linewidth=2, markersize=8)
    for ef, r in zip(ef_values, recalls):
        ax1.annotate(f'{r:.3f}', (ef, r), textcoords="offset points",
                     xytext=(0, 10), ha='center', fontsize=9)
    ax1.set_xlabel('hnsw_ef', fontsize=12)
    ax1.set_ylabel('Recall@100', fontsize=12)
    ax1.set_title('Recall vs ef', fontsize=13)
    ax1.grid(True, alpha=0.3)

    # Serial QPS vs ef
    ax2.plot(ef_values, serial_qps, 'o-', color=colors[1], linewidth=2, markersize=8)
    for ef, q in zip(ef_values, serial_qps):
        ax2.annotate(f'{q:.0f}', (ef, q), textcoords="offset points",
                     xytext=(0, 10), ha='center', fontsize=9)
    ax2.set_xlabel('hnsw_ef', fontsize=12)
    ax2.set_ylabel('Serial QPS', fontsize=12)
    ax2.set_title('Throughput vs ef', fontsize=13)
    ax2.grid(True, alpha=0.3)

    # P99 latency vs ef
    ax3.plot(ef_values, serial_p99, 'o-', color=colors[2], linewidth=2, markersize=8)
    for ef, l in zip(ef_values, serial_p99):
        ax3.annotate(f'{l:.1f}', (ef, l), textcoords="offset points",
                     xytext=(0, 10), ha='center', fontsize=9)
    ax3.set_xlabel('hnsw_ef', fontsize=12)
    ax3.set_ylabel('P99 Latency (ms)', fontsize=12)
    ax3.set_title('Latency vs ef', fontsize=13)
    ax3.grid(True, alpha=0.3)

    plt.suptitle(f'Effect of hnsw_ef (dataset={dataset}, m={m}, ef_c={ef_construct})',
                 fontsize=14, y=1.02)
    plt.tight_layout()
    path = os.path.join(args.output_dir, 'ef_impact.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    print(f"Saved {path}")

    print("\nDone!")


if __name__ == "__main__":
    main()
