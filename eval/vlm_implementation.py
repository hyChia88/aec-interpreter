"""Fine-tuned VLM implementation figure.

This figure is for the "Fine-tuned VLM / perception engine" card. It shows only the VLM
implementation contract and its direct impact, leaving specialist/graph downstream effects to
``vlm_profile.png``.

Run:
    .venv/bin/python eval/vlm_implementation.py

Out:
    output/vlm_implementation.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "output"

INK = "#1a1c20"
MUTED = "#5b6470"
LINE = "#d8dde5"
ORANGE = "#ef7d00"
GREEN = "#2ca02c"
BLUE = "#56B4E9"


def _box(ax, x, y, w, h, title, body="", fc="#ffffff", ec=LINE):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.008,rounding_size=0.020",
            fc=fc,
            ec=ec,
            lw=1.4,
        )
    )
    ax.text(x + w / 2, y + h * 0.70, title, ha="center", va="center", fontsize=13.5, fontweight="bold", color=INK)
    if body:
        ax.text(x + w / 2, y + h * 0.34, body, ha="center", va="center", fontsize=10.2, color=MUTED, linespacing=1.18)


def _arrow(ax, x1, y1, x2, y2, color="#69707a"):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle="-|>",
            mutation_scale=14,
            lw=1.8,
            color=color,
            shrinkA=4,
            shrinkB=4,
        )
    )


def build(out_path: Path):
    fig = plt.figure(figsize=(11.2, 6.0))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    fig.text(0.5, 0.945, "Fine-tuned VLM: implementation and direct impact", ha="center", fontsize=17, fontweight="bold")
    fig.text(0.5, 0.902, "The VLM reads mixed evidence into a typed contract; symbolic retrieval happens after this boundary.",
             ha="center", fontsize=10.5, color=MUTED)

    _box(ax, 0.055, 0.620, 0.185, 0.155, "Input evidence", "site photo\nfield note\nfloorplan patch", fc="#f7f9fc")
    _box(ax, 0.315, 0.620, 0.230, 0.155, "Qwen2.5-VL + LoRA", "fine-tuned on\nsynthetic IFC-grounded cases", fc="#fff4e3", ec=ORANGE)
    _box(ax, 0.620, 0.620, 0.290, 0.155, "Typed Constraints JSON", "{storey, ifc_class,\nspatial_relations[]}\nno database query", fc="#f8fbff", ec=BLUE)
    _arrow(ax, 0.240, 0.697, 0.315, 0.697)
    _arrow(ax, 0.545, 0.697, 0.620, 0.697)

    # A compact output example, because this is the visual convention used for model-card figures.
    ax.add_patch(FancyBboxPatch((0.095, 0.320), 0.405, 0.160, boxstyle="round,pad=0.008,rounding_size=0.014",
                                fc="#ffffff", ec=LINE, lw=1.1))
    ax.text(0.115, 0.445, "example output contract", fontsize=11.5, fontweight="bold", color=INK, ha="left")
    ax.text(
        0.115,
        0.385,
        '{ "storey": "2 - Second Floor",\n  "ifc_class": "IfcWindow",\n  "spatial_relations": [{"predicate": "FILLS", ...}] }',
        fontsize=9.4,
        color="#2a2e35",
        family="monospace",
        ha="left",
        va="center",
    )

    # Direct VLM impact only, not downstream slot/graph effects.
    ax.text(0.610, 0.475, "direct VLM impact", fontsize=12.2, fontweight="bold", color=INK, ha="left")
    y0 = 0.400
    labels = ["zero-shot Gemini", "LoRA fine-tuned VLM"]
    vals = [0, 82]
    colors = ["#b9bec6", ORANGE]
    for i, (lab, val, color) in enumerate(zip(labels, vals, colors)):
        y = y0 - i * 0.095
        ax.text(0.610, y, lab, ha="left", va="center", fontsize=10.4, color=INK)
        ax.plot([0.755, 0.905], [y, y], color="#edf0f4", lw=10, solid_capstyle="round")
        ax.plot([0.755, 0.755 + 0.150 * val / 100], [y, y], color=color, lw=10, solid_capstyle="round")
        ax.text(0.925, y, f"{val}%", ha="left", va="center", fontsize=11.5, fontweight="bold", color=color)
    ax.text(0.610, 0.205, "metric: spatial-direction accuracy on synthetic evaluation", fontsize=8.8, color=MUTED)

    out_path.parent.mkdir(exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("figure →", out_path)


def main():
    build(OUT / "vlm_implementation.png")


if __name__ == "__main__":
    main()
