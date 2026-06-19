"""Section 2.1 figure: four design decisions, each against its MEASURED alternative.

Clean, classic small-multiples: one accent colour for the accepted choice, neutral grey for the
rejected alternative; value labels only; no decorative arrows or call-outs. Every number is from the
paper's own results; where the alternative has no defensible number (a noisy LLM-extracted graph),
the bar is hatched and labelled "unverified" rather than invented.

Run:  .venv/bin/python eval/fig_rationale.py
Out:  output/design_rationale.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "output"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": False,
})

INK = "#1a1c20"
MUTED = "#6b7480"
ALT = "#c7ccd3"      # rejected alternative (neutral grey)
ACCENT = "#2a6f97"   # accepted choice (single calm blue, used throughout)


def _panel(ax, title, metric, alt_label, alt_val, our_label, our_val,
           unit="%", vmax=100, alt_unverified=False):
    ax.set_title(title, fontsize=10.5, fontweight="bold", color=INK, loc="left", pad=26)
    ax.text(0, 1.04, metric, transform=ax.transAxes, fontsize=8.2, color=MUTED, style="italic",
            ha="left", va="bottom")
    ys = [1, 0]
    for y, lab, val, col in ((1, alt_label, alt_val, ALT), (0, our_label, our_val, ACCENT)):
        if y == 1 and alt_unverified:
            ax.barh(y, vmax * 0.18, height=0.5, color="none", edgecolor=ALT, hatch="////", lw=1.0, zorder=3)
            ax.text(vmax * 0.20, y, "unverified", va="center", ha="left", fontsize=8.0,
                    color=MUTED, style="italic")
        else:
            ax.barh(y, val, height=0.5, color=col, zorder=3)
            ax.text(val + vmax * 0.015, y, f"{val:g}{unit}", va="center", ha="left",
                    fontsize=9.0, fontweight=("bold" if y == 0 else "normal"),
                    color=(ACCENT if y == 0 else MUTED))
        ax.text(-vmax * 0.015, y, lab, va="center", ha="right", fontsize=8.6, color=INK)
    ax.set_xlim(0, vmax * 1.30)
    ax.set_ylim(-0.6, 1.6)
    ax.set_xticks([])
    ax.set_yticks([])


def build(out_path: Path):
    fig, axes = plt.subplots(2, 2, figsize=(10.6, 4.9))
    fig.suptitle("Four design decisions, each measured against the alternative it rejects",
                 fontsize=14, fontweight="bold", y=1.0)

    _panel(axes[0, 0], "1.  Neuro-symbolic over end-to-end",
           "pool Top-1, same recall-safe pool",
           "end-to-end learned best", 6.7, "structured address (ours)", 78.5, vmax=100)
    _panel(axes[0, 1], "2.  Deterministic templates over agent",
           "latency per query (lower is better)",
           "ReAct text-to-Cypher agent", 4.5, "templates (ours)", 1.0, unit=" s", vmax=5)
    _panel(axes[1, 0], "3.  IFC-native graph over doc GraphRAG",
           "structural validation vs ground truth",
           "doc GraphRAG (LLM-extracted)", 0, "IFC-native graph (ours)", 100.0, vmax=100,
           alt_unverified=True)
    _panel(axes[1, 1], "4.  LoRA fine-tuning over prompting",
           "predicate slot-accuracy, held-out",
           "zero-shot prompt-only", 43.1, "LoRA fine-tuned (ours)", 84.0, vmax=100)

    # one shared legend, bottom
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(color=ALT, label="rejected alternative"),
                        Patch(color=ACCENT, label="accepted choice (ours)")],
               loc="lower center", ncol=2, frameon=False, fontsize=9, bbox_to_anchor=(0.5, -0.04))

    fig.subplots_adjust(left=0.20, right=0.96, top=0.86, bottom=0.10, hspace=1.0, wspace=0.75)
    out_path.parent.mkdir(exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("figure →", out_path)


if __name__ == "__main__":
    build(OUT / "design_rationale.png")
