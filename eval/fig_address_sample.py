"""Intro figure: what a type-conditional spatial address actually looks like.

A worked sample. Every element gets a coarse ONTOLOGICAL PREFIX (storey + class) that is
necessary but non-discriminating, completed by a class-specific TOPOLOGICAL BODY:
  - fillers (windows/doors) -> a position-slot (i, M): the i-th of M openings along the host wall
  - walls                   -> a connectivity fingerprint (degree, #openings, length band, external?)
The figure shows both as concrete address strings next to a tiny schematic, plus the oracle
ranking lift each one buys (from spatial_address_ceiling.json).

Self-contained: reads only output/spatial_address_ceiling.json.

Run:  .venv/bin/python eval/fig_address_sample.py
Out:  output/address_sample.png
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "output"

INK = "#1a1c20"
MUTED = "#5b6470"
LINE = "#d8dde5"
ORANGE = "#ef7d00"
RED = "#d62728"
BLUE = "#56B4E9"
GREEN = "#2ca02c"
PURPLE = "#9467bd"
WALLCOL = "#3a3f47"

PREFIX_FC = "#eef2f8"
PREFIX_EC = "#9aa7bd"
FILLER_FC = "#fff4e3"
WALL_FC = "#eaf6ff"


def load():
    with open(OUT / "spatial_address_ceiling.json") as f:
        return json.load(f)


def _round(ax, x, y, w, h, fc, ec, lw=1.3, rs=0.012):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.004,rounding_size={rs}",
                                fc=fc, ec=ec, lw=lw, zorder=2))


def build(out_path: Path):
    d = load()
    f = d["metrics_by_subgroup"]["filler"]
    w = d["metrics_by_subgroup"]["wall"]
    coarse_t1 = d["metrics_overall"]["coarse_storey_class"]["top1"]

    fig = plt.figure(figsize=(11.2, 5.4))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    fig.text(0.5, 0.955, "A type-conditional spatial address — one worked sample per element class",
             ha="center", fontsize=14.5, fontweight="bold", color=INK)
    fig.text(0.5, 0.912,
             "coarse ontological prefix (necessary, but non-discriminating)  +  a class-specific topological body (the discriminator)",
             ha="center", fontsize=10, color=MUTED)

    # ---- shared coarse prefix banner ----
    _round(ax, 0.085, 0.775, 0.83, 0.085, PREFIX_FC, PREFIX_EC, lw=1.4)
    ax.text(0.105, 0.835, "PREFIX  (both classes)", fontsize=9, fontweight="bold", color="#5c6b86", ha="left")
    ax.text(0.105, 0.800,
            'storey = "1 - First Floor"   ·   ifc_class = IfcWindow / IfcWall',
            fontsize=10.5, color=INK, ha="left", family="monospace")
    ax.text(0.905, 0.817, f"alone: oracle Top-1 {coarse_t1:g}%", fontsize=9.2, color=RED,
            ha="right", va="center", fontweight="bold")

    # two split arrows down to the two columns
    ax.add_patch(FancyArrowPatch((0.30, 0.775), (0.27, 0.715), arrowstyle="-|>",
                                 mutation_scale=13, lw=1.6, color=MUTED))
    ax.add_patch(FancyArrowPatch((0.70, 0.775), (0.73, 0.715), arrowstyle="-|>",
                                 mutation_scale=13, lw=1.6, color=MUTED))

    # ================= LEFT : FILLER position-slot =================
    lx, lw_, ly, lh = 0.055, 0.42, 0.085, 0.62
    _round(ax, lx, ly, lw_, lh, FILLER_FC, ORANGE, lw=1.6)
    ax.text(lx + 0.02, ly + lh - 0.04, "FILLER  (window / door)", fontsize=11, fontweight="bold", color=ORANGE)
    ax.text(lx + 0.02, ly + lh - 0.075, "body = position-slot  (i, M)", fontsize=9.6, color=INK,
            style="italic")

    # schematic: a host wall with M openings, the i-th highlighted
    wx0, wx1, wy = lx + 0.035, lx + lw_ - 0.035, ly + lh - 0.18
    ax.add_patch(Rectangle((wx0, wy - 0.018), wx1 - wx0, 0.036, fc=WALLCOL, ec="none", zorder=2))
    M = 10; i = 8
    for k in range(M):
        cx = wx0 + (wx1 - wx0) * (k + 0.5) / M
        is_t = (k + 1) == i
        ax.add_patch(Rectangle((cx - 0.011, wy - 0.013), 0.022, 0.026,
                               fc=(ORANGE if is_t else "#ffffff"), ec=(RED if is_t else "#888"),
                               lw=(1.8 if is_t else 1.0), zorder=3))
        if is_t:
            ax.text(cx, wy + 0.05, "target", ha="center", fontsize=7.6, color=RED, fontweight="bold")
            ax.add_patch(FancyArrowPatch((cx, wy + 0.043), (cx, wy + 0.02), arrowstyle="-|>",
                                         mutation_scale=9, lw=1.2, color=RED))
    ax.text((wx0 + wx1) / 2, wy - 0.045, "M = 10 openings along the host wall, numbered in image order",
            ha="center", fontsize=7.8, color=MUTED)

    # the address string
    _round(ax, lx + 0.025, ly + 0.105, lw_ - 0.05, 0.115, "#ffffff", LINE, lw=1.1)
    ax.text(lx + 0.045, ly + 0.187, "address string", fontsize=8.3, fontweight="bold", color=MUTED)
    ax.text(lx + 0.045, ly + 0.135,
            '{ storey:"1-First Floor",\n  class:IfcWindow,\n  slot:(i=8, M=10) }',
            fontsize=8.8, color="#222", family="monospace", va="center", linespacing=1.25)

    ax.text(lx + 0.02, ly + 0.055, f"oracle Top-1:  {coarse_t1:g}%  →  {f['plus_spatial_address']['top1']:g}%",
            fontsize=10.3, color=GREEN, fontweight="bold")
    ax.text(lx + 0.02, ly + 0.022, "image-recoverable → REALIZED 58.9% end-to-end (real detector)",
            fontsize=8.4, color=MUTED, style="italic")

    # ================= RIGHT : WALL fingerprint =================
    rx = 0.525
    _round(ax, rx, ly, lw_, lh, WALL_FC, BLUE, lw=1.6)
    ax.text(rx + 0.02, ly + lh - 0.04, "WALL", fontsize=11, fontweight="bold", color="#1f7bc0")
    ax.text(rx + 0.02, ly + lh - 0.075, "body = connectivity fingerprint", fontsize=9.6, color=INK,
            style="italic")

    # schematic: a central wall with connections + hosted openings
    cx, cy = rx + lw_ / 2, ly + lh - 0.165
    ax.plot([cx - 0.12, cx + 0.12], [cy, cy], color=WALLCOL, lw=7, solid_capstyle="butt", zorder=2)
    # connected walls (degree)
    for dx, dy in [(-0.12, 0.06), (0.12, 0.06), (0.12, -0.06)]:
        ax.plot([cx + (0.12 if dx > 0 else -0.12), cx + dx + (0.05 if dx > 0 else -0.05)],
                [cy, cy + dy], color="#9aa3ad", lw=4, solid_capstyle="round", zorder=1)
    # hosted openings on the wall
    for k in range(2):
        ox = cx - 0.04 + k * 0.08
        ax.add_patch(Rectangle((ox - 0.010, cy - 0.011), 0.020, 0.022, fc="#ffffff", ec="#888", lw=1.0, zorder=3))
    ax.text(cx, cy + 0.05, "degree 3 · 2 openings", ha="center", fontsize=7.8, color=MUTED)
    ax.text(cx, cy - 0.05, "external, length band L", ha="center", fontsize=7.8, color=MUTED)

    _round(ax, rx + 0.025, ly + 0.105, lw_ - 0.05, 0.115, "#ffffff", LINE, lw=1.1)
    ax.text(rx + 0.045, ly + 0.187, "address string", fontsize=8.3, fontweight="bold", color=MUTED)
    ax.text(rx + 0.045, ly + 0.135,
            '{ connection_degree:3,\n  hosted_opening_count:2,\n  length_band:L, is_external:true }',
            fontsize=8.5, color="#222", family="monospace", va="center", linespacing=1.25)

    ax.text(rx + 0.02, ly + 0.055, f"oracle Top-1:  {coarse_t1:g}%  →  {w['plus_spatial_address']['top1']:g}%",
            fontsize=10.3, color=GREEN, fontweight="bold")
    ax.text(rx + 0.02, ly + 0.022, "oracle-discriminative, but NOT image-recoverable (reported at oracle only)",
            fontsize=8.4, color=MUTED, style="italic")

    out_path.parent.mkdir(exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("figure →", out_path)


if __name__ == "__main__":
    build(OUT / "address_sample.png")
