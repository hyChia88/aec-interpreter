"""Focused worked-case figures (clean replacement for the dense 4x3 dashboard).

One case = one left-to-right story:
  (a) inputs          real site photo + human-marked plan
  (b) address         the host wall's M-opening NEXT_TO chain; predicted slot vs true slot
  (c) confidence gate raw -> calibrated, against tau, with ANSWER / DEFER zones shaded
  (d) decision        ANSWER (commit GUID) or DEFER (return candidates)

All per-case values are REAL: the OpenCV position-slot detector, the temperature calibration
(T fit on the held-out fillers), and the GT slot from the position index. Generates a contrasting
pair by default: AP_SK_102 (correct + confident -> ANSWER) and AP_SK_092 (wrong + unsure -> DEFER).

Run:  .venv/bin/python eval/fig_defer_case.py
Out:  output/answer_case.png, output/defer_case.png
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "eval"))
import slot_detector_cv as cv
from rerank_prize import load_index, load_cases, DEFAULT_INDEX, DEFAULT_TRACES
from reconstruct_position_index import load_position_index
from spatial_address_ceiling import DEFAULT_POS
from field_contract import collect_pairs
from calibrate_rerank import fit_temperature, apply_T

OUT = REPO / "output"
DATASET = Path("/home/hychi/projects/cmu/master_thesis/data_curation/datasets/synth_v0.5_ap")
SITE = REPO / "site" / "assets" / "dataset"
TAU = 0.40

INK = "#1a1c20"; MUTED = "#5b6470"; LINE = "#d8dde5"
ORANGE = "#ef7d00"; GREEN = "#2ca02c"; BLUE = "#1f7bc0"; RED = "#d62728"
SIB = "#f4a261"; WALL = "#3a3f47"


def compute_case(cid, idx, cases, pos, gslot, pred, T):
    c = next(x for x in cases if x["scenario_id"] == cid)
    gt = c["scenario"]["ground_truth"]["target_guid"]
    g = gslot[gt]
    pi, pM, raw = pred(c)
    cal = apply_T(raw, T)
    site = SITE / f"{cid}_site.jpg"
    if not site.exists():
        site = DATASET / "imgs" / f"{cid}_site.png"
    return {
        "cid": cid, "pred": (pi, pM), "gt": (g["wall_position_index"], g["wall_child_total"]),
        "raw": raw, "cal": cal, "correct": (pi == g["wall_position_index"] and pM == g["wall_child_total"]),
        "decision": "ANSWER" if cal >= TAU else "DEFER",
        "site": site, "plan": DATASET / "floorplans" / f"{cid}_floorplan.png",
    }


def _img(fig, rect, path, title):
    ax = fig.add_axes(rect)
    try:
        ax.imshow(mpimg.imread(str(path)))
    except FileNotFoundError:
        ax.text(0.5, 0.5, "(missing)", ha="center", va="center")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_edgecolor("#888"); s.set_linewidth(1.6)
    ax.set_title(title, fontsize=8.4, color=INK, fontweight="bold", pad=3)


def _arrow(fig, x0, x1, y=0.52):
    fig.add_artist(FancyArrowPatch((x0, y), (x1, y), transform=fig.transFigure,
                                   arrowstyle="-|>", mutation_scale=18, lw=2.0, color="#555"))


def panel_address(fig, rect, d):
    ax = fig.add_axes(rect); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_aspect("equal"); ax.axis("off")
    pi, M = d["pred"][0], d["pred"][1]
    gi = d["gt"][0]
    r = min(0.052, 0.62 / M)
    fs = max(5.0, min(7.6, 60.0 / M))
    xs = [0.07 + 0.86 * (i / (M - 1)) for i in range(M)] if M > 1 else [0.5]
    ys = [0.62 + 0.05 * math.sin(math.pi * i / max(M - 1, 1)) for i in range(M)]
    ax.plot([0.03, 0.97], [0.28, 0.28], color=WALL, lw=7, solid_capstyle="round", zorder=1)
    for x, y in zip(xs, ys):
        ax.plot([x, x], [y, 0.31], color="#cdb392", lw=0.9, alpha=0.6, zorder=1)
    ax.text(0.5, 0.17, f"host wall — {M} openings (NEXT_TO chain)", ha="center", fontsize=7.4,
            color=WALL, fontweight="bold")
    for a in range(M - 1):
        ax.plot([xs[a], xs[a + 1]], [ys[a], ys[a + 1]], color=ORANGE, lw=1.6, alpha=0.85, zorder=2)
    for i in range(M):
        idx, x, y = i, xs[i], ys[i]
        is_pred, is_gt = (idx == pi), (idx == gi)
        if d["correct"] and is_pred:
            ax.add_patch(Circle((x, y), r * 1.25, fc=GREEN, ec=INK, lw=1.5, zorder=6))
            ax.text(x, y, "✓", ha="center", va="center", fontsize=fs + 2, color="white", fontweight="bold", zorder=7)
            ax.annotate(f"predicted = true\nslot {idx}", xy=(x, y + r), xytext=(x, y + 0.25),
                        ha="center", fontsize=7.6, color=GREEN, fontweight="bold",
                        arrowprops=dict(arrowstyle="-|>", color=GREEN, lw=1.0), zorder=8)
        elif is_pred:
            ax.add_patch(Circle((x, y), r * 1.25, fc=RED, ec=INK, lw=1.5, zorder=6))
            ax.text(x, y, "✗", ha="center", va="center", fontsize=fs + 1, color="white", fontweight="bold", zorder=7)
            ax.annotate(f"predicted\nslot {idx}", xy=(x, y + r), xytext=(x, y + 0.25),
                        ha="center", fontsize=7.6, color=RED, fontweight="bold",
                        arrowprops=dict(arrowstyle="-|>", color=RED, lw=1.0), zorder=8)
        elif is_gt:
            ax.add_patch(Circle((x, y), r * 1.1, fc="white", ec=GREEN, lw=2.2, zorder=5))
            ax.text(x, y, str(idx), ha="center", va="center", fontsize=fs, color=GREEN, fontweight="bold", zorder=6)
            ax.annotate(f"true\nslot {idx}", xy=(x, y + r), xytext=(x, y + 0.25),
                        ha="center", fontsize=7.6, color=GREEN, fontweight="bold",
                        arrowprops=dict(arrowstyle="-|>", color=GREEN, lw=1.0), zorder=8)
        else:
            ax.add_patch(Circle((x, y), r, fc=SIB, ec="#c47d33", lw=0.6, zorder=4))
            ax.text(x, y, str(idx), ha="center", va="center", fontsize=fs - 1, color="#5a3c14", zorder=5)
    head = (f"(b)  predicted slot {pi} ✓ (= true)" if d["correct"]
            else f"(b)  predicted slot {pi} ✗  vs true slot {gi}")
    ax.set_title(head, fontsize=9.0, fontweight="bold", color=INK, pad=2)


def panel_gate(fig, rect, d):
    ax = fig.add_axes(rect); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.axvspan(0, TAU, color="#fdeaea", zorder=0)
    ax.axvspan(TAU, 1, color="#eaf6ee", zorder=0)
    ax.axvline(TAU, color="#555", lw=1.4, ls=(0, (4, 3)), zorder=2)
    ax.text(TAU + 0.02, 0.93, f"τ={TAU:.2f}", color="#444", fontsize=8.0, fontweight="bold", va="top")
    ax.text(TAU / 2, 0.07, "DEFER", color="#b03030", fontsize=7.6, ha="center", style="italic")
    ax.text((TAU + 1) / 2, 0.07, "ANSWER", color="#2a7d46", fontsize=7.6, ha="center", style="italic")
    col = GREEN if d["decision"] == "ANSWER" else BLUE
    ax.scatter([d["raw"]], [0.55], s=60, color="#b9bec6", zorder=3)
    ax.text(d["raw"], 0.67, f"raw\n{d['raw']:.2f}", ha="center", fontsize=7.0, color=MUTED)
    ax.scatter([d["cal"]], [0.55], s=110, color=col, zorder=4, edgecolor="white", lw=1.0)
    ax.text(d["cal"], 0.40, f"calibrated\n{d['cal']:.2f}", ha="center", va="top", fontsize=7.4,
            color=col, fontweight="bold")
    ax.annotate("", xy=(d["cal"], 0.55), xytext=(d["raw"], 0.55),
                arrowprops=dict(arrowstyle="-|>", color="#888", lw=1.1), zorder=3)
    ax.set_yticks([]); ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0]); ax.tick_params(labelsize=7)
    ax.set_xlabel("detector confidence", fontsize=8.2)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.set_title("(c)  calibration gate", fontsize=9.0, fontweight="bold", color=INK, pad=4)


def panel_decision(fig, rect, d):
    ax = fig.add_axes(rect); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.set_title("(d)  decision", fontsize=9.0, fontweight="bold", color=INK, pad=4)
    is_ans = d["decision"] == "ANSWER"
    # top = ANSWER, bottom = DEFER; active one is filled, the other greyed
    for y0, label, sub, active, col in [
        (0.60, "ANSWER", "commit GUID", is_ans, GREEN),
        (0.30, "DEFER", "→ return candidates", not is_ans, RED)]:
        fc = col if active else "#f1f3f6"
        tc = "white" if active else "#9aa3ad"
        ax.add_patch(FancyBboxPatch((0.06, y0), 0.88, 0.20, boxstyle="round,pad=0.01,rounding_size=0.04",
                                    fc=fc, ec=(LINE if not active else "none"), lw=1.2))
        ax.text(0.5, y0 + 0.125, label, ha="center", va="center", fontsize=10.0, color=tc, fontweight="bold")
        ax.text(0.5, y0 + 0.045, sub, ha="center", va="center", fontsize=7.6, color=tc)
    note = (f"conf {d['cal']:.2f} ≥ τ {TAU:.2f}\n→ confident & correct, commit"
            if is_ans else f"conf {d['cal']:.2f} < τ {TAU:.2f}\n→ surfaces the pool, not a\nconfident wrong GUID")
    ax.text(0.5, 0.13, note, ha="center", va="center", fontsize=7.6, color=MUTED, linespacing=1.3)


def build(d, out_path):
    verb = "correct & confident → commit" if d["decision"] == "ANSWER" else "wrong, but low confidence → abstain"
    fig = plt.figure(figsize=(13.0, 4.0))
    fig.text(0.5, 0.95, f"A worked {d['decision']} case ({d['cid']}): {verb}",
             ha="center", fontsize=14, fontweight="bold", color=INK)
    _img(fig, [0.015, 0.46, 0.135, 0.34], d["site"], "(a) site photo")
    _img(fig, [0.015, 0.10, 0.135, 0.30], d["plan"], "marked plan (target red)")
    _arrow(fig, 0.155, 0.185)
    panel_address(fig, [0.205, 0.16, 0.30, 0.66], d)
    _arrow(fig, 0.515, 0.545)
    panel_gate(fig, [0.565, 0.26, 0.20, 0.46], d)
    _arrow(fig, 0.775, 0.805)
    panel_decision(fig, [0.815, 0.20, 0.175, 0.58], d)
    out_path.parent.mkdir(exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("figure →", out_path)


def main():
    idx = load_index(DEFAULT_INDEX); cases = load_cases(DEFAULT_TRACES); pos = load_position_index(DEFAULT_POS)
    gslot = cv.build_global_slot(idx, pos); pred = cv.make_predictor(idx)
    fill = [c for c in cases if c["scenario"]["ground_truth"]["target_guid"] in pos]
    T = fit_temperature(collect_pairs(pred, fill, gslot))
    for cid, name in [("AP_SK_102", "answer_case"), ("AP_SK_092", "defer_case")]:
        d = compute_case(cid, idx, cases, pos, gslot, pred, T)
        print(cid, {k: d[k] for k in ("pred", "gt", "raw", "cal", "correct", "decision")})
        build(d, OUT / f"{name}.png")


if __name__ == "__main__":
    main()
