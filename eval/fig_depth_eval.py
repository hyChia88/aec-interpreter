"""Regenerate output/depth_saturation.png with the CORRECTED depth-law mechanism.

Reads the existing output/depth_saturation.json for the oracle |C| by depth (measured), and overlays
the measured G8 per-hop relation-type recovery on AP held-out (96.7/93.9/69.6%, from
remeasure_2026-06-14.json). Replaces the old synthetic "realizable |C|" curve (which used a prior,
weaker model's per-hop predicate reliability) with the honest message: oracle |C| is a singleton by
one hop, recovery does NOT collapse with depth, and saturation is informational (type-homogeneity).

Run:  .venv/bin/python eval/fig_depth_eval.py
Out:  output/depth_saturation.png
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "output"
PURPLE = "#9467bd"
ORANGE = "#ef7d00"
MUTED = "#5b6470"
RECOVERY = {1: 96.7, 2: 93.9, 3: 69.6}  # measured G8 per-hop type-recovery on AP held-out


def main():
    d = json.load(open(OUT / "depth_saturation.json"))
    oracle = d["oracle_median_pool_by_depth"]
    depths = [0, 1, 2, 3]
    oc = [oracle[str(k)] for k in depths]

    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ax.plot(depths, oc, "o-", color=PURPLE, lw=2.2, ms=7, zorder=5,
            label="oracle |C| (graph-side discrimination)")
    for x, y in zip(depths, oc):
        ax.annotate(f"{y:g}", (x, y), textcoords="offset points", xytext=(0, 8), ha="center",
                    fontsize=8.4, color=PURPLE, fontweight="bold")
    ax.set_ylim(-0.6, 14.5)
    ax.set_xlim(-0.15, 3.15)
    ax.set_xticks(depths)
    ax.set_xlabel("relational depth (hops)")
    ax.set_ylabel("oracle confusable-set size  |C|", color=PURPLE)
    ax.tick_params(axis="y", labelcolor=PURPLE)
    ax.spines["top"].set_visible(False)
    ax.grid(axis="y", alpha=0.13)

    ax2 = ax.twinx()
    xs = [1, 2, 3]
    rec = [RECOVERY[k] for k in xs]
    ax2.bar(xs, rec, width=0.34, color=ORANGE, alpha=0.55, zorder=2,
            label="G8 reads relation type (%)")
    for x, v in zip(xs, rec):
        ax2.text(x, v + 2, f"{v:.0f}%", ha="center", fontsize=8.0, color="#b5651d", fontweight="bold")
    ax2.set_ylim(0, 119)
    ax2.set_ylabel("G8 per-hop type-recovery (%)", color="#b5651d")
    ax2.tick_params(axis="y", labelcolor="#b5651d")
    ax2.spines["top"].set_visible(False)

    ax.axvline(1, color=MUTED, lw=1.0, ls=(0, (2, 3)), zorder=1)
    ax.text(1.07, 12.6, "oracle already singleton", fontsize=8.0, color=MUTED, va="top", style="italic")

    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper center", fontsize=8, frameon=False)
    ax.set_title("Depth law (measured): recovery stays high, but recovered relations don't discriminate",
                 fontsize=10, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT / "depth_saturation.png", dpi=150)
    print("figure → output/depth_saturation.png")


if __name__ == "__main__":
    main()
