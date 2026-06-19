"""Candidate-pool collapse — how many elements must a coordinator actually consider?

We report a transparent, fully data-derived quantity: the **median candidate pool size**
the coordinator is handed at each filtering stage of the SAME retrieved pool.

  retrieved pool      : the recall-safe pool the symbolic cascade returns (GT in-pool 100%)
  + storey & class    : the confusable subset sharing the target's storey and IFC class
  + spatial address   : the subset that also matches the type-conditional address (oracle)

This is a measured pool size, not a time/effort or user-study claim: we previously framed it
as an inspection-time proxy, but we have no investigation-time data, so we report pool size only.

Run:  .venv/bin/python eval/triage_effort.py  ->  output/triage_effort.{png,json} + ledger row.
"""
from __future__ import annotations

import json
import statistics as st
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
from rerank_prize import (load_index, load_cases, pool_candidates,
                          DEFAULT_INDEX, DEFAULT_TRACES)
from reconstruct_position_index import load_position_index
from wall_fingerprint import load_wall_fingerprint
from spatial_address_ceiling import score, DEFAULT_POS, DEFAULT_WALL

REPO = EVAL.parent
OUT = REPO / "output"

# stage -> (label, weights whose full match defines the surviving confusable subset)
STAGES = [
    ("retrieved pool", None),
    ("+ storey & class", {"storey": 1, "ifc_class": 1}),
    ("+ spatial address", {"storey": 1, "ifc_class": 1, "spatial_address": 1}),
]


def main():
    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    wallfp = load_wall_fingerprint(DEFAULT_WALL)

    sizes = {label: [] for label, _ in STAGES}
    n = 0
    for c in cases:
        gt = c["scenario"]["ground_truth"]["target_guid"]
        pool = pool_candidates(c)
        if gt not in pool:
            continue
        n += 1
        for label, w in STAGES:
            if w is None:
                sizes[label].append(len(pool))
            else:
                sc = score(pool, idx, pos, wallfp, gt, w)
                full = sum(w.values())
                sizes[label].append(sum(1 for g in pool if sc[g] == full))

    rows = {}
    for label, _ in STAGES:
        v = sizes[label]
        rows[label] = {"n": n, "median_pool": st.median(v), "mean_pool": round(st.mean(v), 1),
                       "min_pool": min(v), "max_pool": max(v)}

    OUT.mkdir(exist_ok=True)
    json.dump(rows, open(OUT / "triage_effort.json", "w"), indent=2)
    _figure(rows)

    print(f"\n{'stage':<20}{'median':>8}{'mean':>7}{'min':>5}{'max':>5}")
    for label, m in rows.items():
        print(f"{label:<20}{m['median_pool']:>8.0f}{m['mean_pool']:>7.1f}{m['min_pool']:>5}{m['max_pool']:>5}")
    a, b = rows[STAGES[0][0]]["median_pool"], rows[STAGES[-1][0]]["median_pool"]
    print(f"\nmedian candidate pool collapses {a:.0f} -> {b:.0f} as ontology then the spatial address are applied.")


def _figure(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = list(rows)
    med = [rows[l]["median_pool"] for l in labels]
    colors = ["#9aa3af", "#7fb3d5", "#9467bd"]

    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    bars = ax.bar(range(len(labels)), med, color=colors, width=0.62, zorder=3)
    for b, l in zip(bars, labels):
        v = rows[l]["median_pool"]
        ax.text(b.get_x() + b.get_width() / 2, v + max(med) * 0.025, f"{v:.0f}",
                ha="center", va="bottom", fontsize=13, fontweight="bold")
    # collapse arrows between bars
    for i in range(len(labels) - 1):
        ax.annotate("", xy=(i + 0.78, med[i + 1] + max(med) * 0.06),
                    xytext=(i + 0.22, med[i] * 0.6),
                    arrowprops=dict(arrowstyle="-|>", color="#5c6470", lw=1.6))
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=10.5)
    ax.set_ylabel("median candidate pool size", fontsize=10.5)
    ax.set_ylim(0, max(med) * 1.15)
    ax.set_title("Candidate pool the coordinator must review\n"
                 f"median size collapses {med[0]:.0f} → {med[-1]:.0f} as ontology, then the spatial address, are applied",
                 fontsize=11)
    ax.grid(axis="y", color="#e6e8ec", zorder=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "triage_effort.png", dpi=150)
    print("figure ->", OUT / "triage_effort.png")


if __name__ == "__main__":
    main()
