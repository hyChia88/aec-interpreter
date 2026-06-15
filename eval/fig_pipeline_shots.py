"""Figure 1 (rebuilt): the method spine, screenshot-forward.

Real artefacts dominate; the spine boxes are connective tissue. Worked on one held-out case
(AP_SK_107), every tile is a true image off disk:
  (a) Inputs       site photo + human-marked plan (target=red, anchor=orange) + the NL note
  (b) Perception   the OpenCV slot detector's real overlay (green openings on the host wall,
                   red target cross) + the {value, confidence, source} record it emits
  (c) Address      the depth-1 structured spatial-address record (auditable)
  (d) Routing      the calibration gate -> selective ANSWER / DEFER
  (e) Grounding    match the address against the IFC-graph pool -> ranked GUID

Run:  .venv/bin/python eval/fig_pipeline_shots.py
Out:  output/pipeline_shots.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "output"
PROBE = OUT / "_probe"
SITE = REPO / "site" / "assets" / "dataset"

INK = "#1a1c20"
MUTED = "#5b6470"
LINE = "#d8dde5"
ORANGE = "#ef7d00"
GREEN = "#2ca02c"
BLUE = "#1f7bc0"
RED = "#d62728"

CASE = "AP_SK_107"


def _img_ax(fig, rect, path, title=None, frame=ORANGE):
    ax = fig.add_axes(rect)
    try:
        ax.imshow(mpimg.imread(str(path)))
    except FileNotFoundError:
        ax.text(0.5, 0.5, "(missing)", ha="center", va="center", color=RED)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_edgecolor(frame); s.set_linewidth(2.0)
    if title:
        ax.set_title(title, fontsize=8.6, color=INK, fontweight="bold", pad=3)
    return ax


def _stagebar(fig, x, label):
    fig.text(x, 0.045, label, ha="center", fontsize=9.4, color=INK, fontweight="bold")


def _arrow(fig, x0, x1, y=0.5):
    fig.add_artist(FancyArrowPatch((x0, y), (x1, y), transform=fig.transFigure,
                                   arrowstyle="-|>", mutation_scale=18, lw=2.2, color="#555"))


def _card(fig, rect, lines, ec=LINE, title=None, title_col=INK, mono=True):
    ax = fig.add_axes(rect); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.add_patch(FancyBboxPatch((0.02, 0.02), 0.96, 0.96, boxstyle="round,pad=0.02,rounding_size=0.06",
                                fc="#ffffff", ec=ec, lw=1.4))
    y = 0.84
    if title:
        ax.text(0.1, y, title, fontsize=8.4, fontweight="bold", color=title_col, ha="left")
        y -= 0.16
    for ln, col, fs in lines:
        ax.text(0.1, y, ln, fontsize=fs, color=col, ha="left", va="center",
                family=("monospace" if mono else "sans-serif"))
        y -= 0.155
    return ax


def build(out_path: Path):
    fig = plt.figure(figsize=(13.2, 4.5))
    fig.text(0.5, 0.955, "The method spine — one held-out case, end to end",
             ha="center", fontsize=14.5, fontweight="bold", color=INK)
    fig.text(0.5, 0.915,
             "neural layer describes evidence · symbolic layer alone names GUIDs · confidence routes ANSWER vs DEFER",
             ha="center", fontsize=8.8, color=MUTED)

    # ---- (a) inputs: site photo + marked plan, stacked ----
    _img_ax(fig, [0.015, 0.46, 0.155, 0.40], SITE / f"{CASE}_site.jpg", "site photo", frame="#888")
    _img_ax(fig, [0.015, 0.12, 0.155, 0.31], PROBE / f"{CASE}_plan.png", "human-marked plan", frame="#888")
    fig.text(0.092, 0.085, '"check the window on this wall"', ha="center", fontsize=7.2,
             color=MUTED, style="italic")
    _stagebar(fig, 0.092, "(a) inputs")
    _arrow(fig, 0.175, 0.205)

    # ---- (b) perception: detector overlay (big) + record ----
    _img_ax(fig, [0.215, 0.30, 0.215, 0.56], PROBE / f"{CASE}_detect.png",
            "OpenCV detector: openings·host wall·target(+)", frame=ORANGE)
    _card(fig, [0.225, 0.085, 0.195, 0.18],
          [("value : slot (i, M)", INK, 7.6),
           ("confidence : 0.64", INK, 7.6),
           ("source : opencv_slot", MUTED, 7.4)],
          ec=ORANGE, title="per-field record", title_col=ORANGE)
    _stagebar(fig, 0.32, "(b) perception")
    _arrow(fig, 0.435, 0.465)

    # ---- (c) structured address record ----
    _card(fig, [0.475, 0.30, 0.165, 0.50],
          [("storey : 1-First Flr", INK, 8.0),
           ("class  : IfcWindow", INK, 8.0),
           ("slot   : (i, M)", INK, 8.0),
           ("", INK, 6.0),
           ("depth-1, auditable", GREEN, 7.6)],
          ec=BLUE, title="structured address", title_col=BLUE)
    _stagebar(fig, 0.557, "(c) address")
    _arrow(fig, 0.645, 0.675)

    # ---- (d) calibrated routing gate ----
    axd = fig.add_axes([0.685, 0.30, 0.135, 0.50]); axd.set_xlim(0, 1); axd.set_ylim(0, 1); axd.axis("off")
    axd.add_patch(FancyBboxPatch((0.04, 0.04), 0.92, 0.92, boxstyle="round,pad=0.02,rounding_size=0.06",
                                 fc="#f7f9fc", ec=BLUE, lw=1.4))
    axd.text(0.5, 0.86, "calibration gate", ha="center", fontsize=8.4, fontweight="bold", color=BLUE)
    axd.text(0.5, 0.72, "conf ≥ τ ?", ha="center", fontsize=8.6, color=INK, family="monospace")
    axd.add_patch(FancyBboxPatch((0.12, 0.40), 0.76, 0.16, boxstyle="round,pad=0.01,rounding_size=0.05",
                                 fc=GREEN, ec="none"))
    axd.text(0.5, 0.48, "ANSWER", ha="center", va="center", fontsize=8.6, color="white", fontweight="bold")
    axd.add_patch(FancyBboxPatch((0.12, 0.14), 0.76, 0.16, boxstyle="round,pad=0.01,rounding_size=0.05",
                                 fc="#ffffff", ec=RED, lw=1.4))
    axd.text(0.5, 0.22, "DEFER", ha="center", va="center", fontsize=8.6, color=RED, fontweight="bold")
    _stagebar(fig, 0.752, "(d) routing")
    _arrow(fig, 0.825, 0.855)

    # ---- (e) grounding: ranked GUID shortlist ----
    axe = fig.add_axes([0.862, 0.30, 0.128, 0.50]); axe.set_xlim(0, 1); axe.set_ylim(0, 1); axe.axis("off")
    axe.add_patch(FancyBboxPatch((0.04, 0.04), 0.92, 0.92, boxstyle="round,pad=0.02,rounding_size=0.06",
                                 fc="#ffffff", ec=GREEN, lw=1.6))
    axe.text(0.5, 0.86, "ranked GUIDs", ha="center", fontsize=8.4, fontweight="bold", color=GREEN)
    axe.text(0.5, 0.75, "pool 76 → top-k", ha="center", fontsize=7.2, color=MUTED)
    rows = [("1", "3kQ8c… ✓", True), ("2", "0aFb2…", False), ("3", "9zP1k…", False)]
    for i, (r, g, hit) in enumerate(rows):
        y = 0.60 - i * 0.15
        fc = "#e9f7ec" if hit else "#ffffff"
        axe.add_patch(FancyBboxPatch((0.1, y - 0.06), 0.8, 0.115, boxstyle="round,pad=0.006,rounding_size=0.03",
                                     fc=fc, ec=(GREEN if hit else LINE), lw=(1.4 if hit else 0.9)))
        axe.text(0.16, y, r, fontsize=7.6, fontweight="bold", color=(GREEN if hit else MUTED), va="center")
        axe.text(0.30, y, g, fontsize=7.4, color=INK, va="center", family="monospace")
    _stagebar(fig, 0.926, "(e) grounding")

    out_path.parent.mkdir(exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("figure →", out_path)


if __name__ == "__main__":
    build(OUT / "pipeline_shots.png")
