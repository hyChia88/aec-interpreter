"""Figure 7 (rebuilt, 2-panel): the fine-tuned VLM perception engine — what it learned, measured.

Built entirely from measured numbers in the repo (no fabricated loss curve).

  (A) Per-field accuracy, ordered coarse -> discriminating, in ONE plot (merges the old gains +
      held-out-recovery panels): zero-shot prompt-only vs LoRA fine-tuned. Fine-tuning saturates the
      coarse prefix (storey, class) and learns relation typing, but the discriminating address fields
      (position-slot, size band) stay at 0% even fine-tuned -> delegate to deterministic specialists.
  (B) Calibration reliability diagram of the realized detector confidence (AUROC / ECE) -- the gate
      that makes confidence-routing legitimate.

Sources: output/vlm_profile.json, output/calibration_diag.json, paper field-accuracy numbers.

Run:  .venv/bin/python eval/fig_vlm_finetune.py
Out:  output/vlm_finetune.png
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "output"

INK = "#1a1c20"
MUTED = "#5b6470"
LINE = "#d8dde5"
GREY = "#c2c8d0"
ORANGE = "#ef7d00"
GREEN = "#2ca02c"
BLUE = "#1f7bc0"
RED = "#d62728"


def load():
    prof = json.load(open(OUT / "vlm_profile.json"))
    cal = json.load(open(OUT / "calibration_diag.json"))
    return prof, cal


def panel_fields(ax):
    # ordered coarse (left) -> discriminating (right); zero-shot vs fine-tuned/held-out
    fields = ["storey", "ifc_class", "predicate", "relation\ndir.", "position\nslot", "size\nband"]
    zs = [30.0, 63.3, 43.1, 0.0, 0.0, 0.0]
    ft = [100.0, 100.0, 84.0, 82.1, 0.0, 0.0]   # position-slot / size: 0% even fine-tuned (held-out)
    x = np.arange(len(fields))
    w = 0.40
    ax.bar(x - w / 2, zs, w, color=GREY, label="zero-shot (prompt-only)", zorder=3)
    ax.bar(x + w / 2, ft, w, color=ORANGE, label="LoRA fine-tuned", zorder=3)
    for xi, v in zip(x, zs):
        ax.text(xi - w / 2, v + 1.5, ("0" if v < 1 else f"{v:g}"), ha="center", va="bottom",
                fontsize=7.4, color="#6b7480")
    for xi, v in zip(x, ft):
        ax.text(xi + w / 2, v + 1.5, ("0" if v < 1 else f"{v:g}"), ha="center", va="bottom",
                fontsize=7.8, color="#b5651d", fontweight="bold")

    # divider between coarse/relational (VLM reliable) and discriminating (delegate)
    ax.axvline(3.5, color=MUTED, lw=1.0, ls=(0, (3, 3)), zorder=1)
    ax.text(1.75, 109, "coarse + relation typing\n(VLM is reliable)", ha="center", va="top",
            fontsize=8.0, color=GREEN, fontweight="bold")
    ax.text(4.5, 109, "discriminating fields\n(delegate to specialists)", ha="center", va="top",
            fontsize=8.0, color=RED, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(fields, fontsize=8.4)
    ax.set_ylim(0, 118)
    ax.set_ylabel("accuracy (%)", fontsize=9.5)
    ax.set_title("(A)  Fine-tuning saturates coarse fields, fails on discriminating ones",
                 fontsize=10, fontweight="bold", loc="left", pad=6)
    ax.legend(fontsize=8.0, frameon=False, loc="center right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.13)


def panel_calibration(ax, cal):
    bins = [b for b in cal["bins"] if b["n"] > 0]
    conf = [b["conf"] for b in bins]
    acc = [b["acc"] for b in bins]
    ns = [b["n"] for b in bins]
    ax.plot([0, 1], [0, 1], color=MUTED, ls=(0, (3, 3)), lw=1.1, zorder=1, label="perfect calibration")
    ax.scatter(conf, acc, s=[45 + 22 * n for n in ns], color=BLUE, edgecolor="white",
               lw=1.0, zorder=3, label="bin (size ∝ n)")
    ax.plot(conf, acc, color=BLUE, lw=1.6, zorder=2)
    for c, a, n in zip(conf, acc, ns):
        ax.text(c, a + 0.05, f"n={n}", ha="center", fontsize=7.0, color=MUTED)
    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 1.08)
    ax.set_xlabel("detector confidence", fontsize=9.5)
    ax.set_ylabel("empirical accuracy", fontsize=9.5)
    ax.set_title("(B)  Detector confidence is calibratable → routing is legitimate",
                 fontsize=10, fontweight="bold", loc="left", pad=6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(alpha=0.13)
    ax.legend(fontsize=7.6, frameon=False, loc="upper left")
    txt = (f"AUROC {cal['auroc']:.2f}  (CI {cal['auroc_ci95'][0]:.2f}–{cal['auroc_ci95'][1]:.2f})\n"
           f"ECE {cal['ece']:.3f} → 0.172 (temp. scaling)")
    ax.text(0.97, 0.06, txt, transform=ax.transAxes, ha="right", va="bottom", fontsize=7.8,
            color=INK, bbox=dict(boxstyle="round,pad=0.4", fc="#f7f9fc", ec=LINE))


def build(out_path: Path):
    prof, cal = load()
    fig = plt.figure(figsize=(12.0, 4.3))
    fig.text(0.5, 0.965, "Fine-tuned VLM perception engine: what it learned, measured",
             ha="center", fontsize=14, fontweight="bold", color=INK)
    fig.text(0.5, 0.905,
             "Qwen2.5-VL-7B + LoRA (r=32, Q/K/V/O+MLP on vision encoder & LM)  ·  990 synthetic IFC-grounded cases  ·  emits typed JSON only",
             ha="center", fontsize=8.6, color=MUTED)

    axA = fig.add_axes([0.065, 0.14, 0.515, 0.66])
    axB = fig.add_axes([0.685, 0.14, 0.285, 0.66])
    panel_fields(axA)
    panel_calibration(axB, cal)

    out_path.parent.mkdir(exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("figure →", out_path)


if __name__ == "__main__":
    build(OUT / "vlm_finetune.png")
