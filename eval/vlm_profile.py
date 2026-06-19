"""Re-evaluate the fine-tuned VLM (G8) per-field — what it extracts well vs where it fails.

Decides "how to improve the VLM": the profile shows the LoRA-fine-tuned Qwen2.5-VL (G8) nails the
COARSE prefix (storey + ifc_class, 100%) — the saturated, non-discriminating part — but fails on
the DISCRIMINATING structured fields (position-slot 0%, size 0%; direction partial). The lesson is
architectural, not "fine-tune harder": delegate the slot/size to the deterministic visual
specialists (M1b / ResNet, which realize them) and keep the VLM on coarse + relations. Direct
evidence for the neuro-symbolic interface — learning where the net is reliable, deterministic
specialists where it is not.

Run:  .venv/bin/python eval/vlm_profile.py   →  output/vlm_profile.{png,json}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
from rerank_prize import load_index, load_cases, DEFAULT_INDEX, DEFAULT_TRACES

OUT = EVAL.parent / "output"


def _norm(s) -> str:
    return str(s or "").lower().replace("ifc", "").strip()


def profile(idx, cases) -> dict:
    n = len(cases)
    c = {k: 0 for k in ("storey_ex", "storey_ok", "class_ex", "class_ok", "slot_ex", "rel", "dir", "size_ex")}
    for case in cases:
        gt = case["scenario"]["ground_truth"]["target_guid"]; e = idx.get(gt, {})
        con = case.get("internals", {}).get("constraints", {}) or {}
        s = con.get("storey_name")
        c["storey_ex"] += s not in (None, "")
        if s and _norm(e.get("storey_name")).find((_norm(s).split() or ["zzz"])[0]) >= 0:
            c["storey_ok"] += 1
        cl = con.get("ifc_class")
        c["class_ex"] += cl not in (None, ""); c["class_ok"] += _norm(cl) == _norm(e.get("ifc_class"))
        c["slot_ex"] += con.get("position_context") not in (None, "")
        rels = con.get("spatial_relations") or []
        c["rel"] += len(rels) > 0; c["dir"] += any(r.get("direction") for r in rels)
        c["size_ex"] += (con.get("target_width_mm") or con.get("target_height_mm")) not in (None, "")
    return {"n": n, **{k: round(100 * v / n, 1) for k, v in c.items()}}


INK = "#1a1c20"
MUTED = "#5b6470"
ORANGE = "#ef7d00"       # VLM-reliable coarse fields
AMBER = "#f4a93d"        # partial
GREY = "#c2c8d0"         # needs deterministic specialist


# Per-field EXTRACTION ACCURACY (correct value vs ground truth), fine-tuned G8 vs zero-shot
# Gemini, the foundational comparator. Provenance: paper sec. eval-neural / thesis ch.7 Track-G
#   storey:    G8 100  | Gemini 30.0   (storey_name normalized match)
#   IFC class: G8 100  | Gemini 63.3   (ifc_class match; dataset-level ceiling for zero-shot)
#   predicate: G8 82.8 | Gemini 43.1   (spatial-relation predicate slot accuracy)
#   direction: G8 82.1 | Gemini  0.0   (relation direction; emerges only with fine-tuning)
#   slot/size: 0/0 for BOTH            -> delegated to the deterministic visual specialists
# (G8's storey/class accuracy equals its field-population rate in output/vlm_profile.json;
#  the 56.7% direction figure there is an EMISSION rate, a different quantity from the 82.1%
#  direction ACCURACY shown here.)
ACC_FIELDS = [
    ("storey",              100.0, 30.0, ORANGE),
    ("IFC class",           100.0, 63.3, ORANGE),
    ("spatial\npredicate",   82.8, 43.1, ORANGE),
    ("relation\ndirection",  82.1,  0.0, AMBER),
    ("position\nslot",        0.0,  0.0, GREY),
    ("size\nband",            0.0,  0.0, GREY),
]
GEMINI_C = "#9aa3af"


def make_figure(p, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = [f[0] for f in ACC_FIELDS]
    g8 = [f[1] for f in ACC_FIELDS]
    gem = [f[2] for f in ACC_FIELDS]
    g8_colors = [f[3] for f in ACC_FIELDS]

    fig, ax = plt.subplots(figsize=(9.8, 4.6))
    fig.suptitle("Per-field extraction accuracy: fine-tuning (G8) vs zero-shot Gemini",
                 fontsize=14, fontweight="bold", y=1.02)
    fig.text(0.5, 0.93,
             f"held-out benchmark (n={p['n']}); fine-tuning saturates the coarse prefix and "
             "recovers relations, where zero-shot Gemini fails",
             ha="center", fontsize=9.4, color=MUTED)

    import numpy as np
    x = np.arange(len(ACC_FIELDS)); w = 0.38
    ax.bar(x - w / 2, g8, width=w, color=g8_colors, zorder=3, label="fine-tuned VLM (G8)")
    ax.bar(x + w / 2, gem, width=w, color=GEMINI_C, zorder=3, label="zero-shot Gemini")
    for xi, v in zip(x, g8):
        ax.text(xi - w / 2, v + 2.2, ("0" if v < 1 else f"{v:g}"), ha="center", va="bottom",
                fontsize=9, fontweight="bold", color=INK)
    for xi, v in zip(x, gem):
        ax.text(xi + w / 2, v + 2.2, ("0" if v < 1 else f"{v:g}"), ha="center", va="bottom",
                fontsize=9, color=MUTED)
    # mark the specialist-delegated fields (0% for both models)
    for xi, f in zip(x, ACC_FIELDS):
        if f[3] == GREY:
            ax.text(xi, 9, "→ deterministic\nspecialist", ha="center", va="bottom",
                    fontsize=7.6, color=MUTED, style="italic")

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=9.6)
    ax.set_ylim(0, 112)
    ax.set_ylabel("field extracted correctly (%)", fontsize=10)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.grid(axis="y", color="#e5e8ee", lw=0.8, zorder=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)

    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(color=ORANGE, label="fine-tuned VLM (G8)"),
                        Patch(color=GEMINI_C, label="zero-shot Gemini"),
                        Patch(color=GREY, label="0% for both → specialist")],
               loc="lower center", ncol=3, frameon=False, fontsize=8.8, bbox_to_anchor=(0.5, -0.05))

    fig.tight_layout(rect=[0, 0.05, 1, 0.9])
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    print("figure →", out_path)


def main():
    idx = load_index(DEFAULT_INDEX); cases = load_cases(DEFAULT_TRACES)
    p = profile(idx, cases)
    OUT.mkdir(exist_ok=True)
    json.dump(p, open(OUT / "vlm_profile.json", "w"), indent=2)
    make_figure(p, OUT / "vlm_profile.png")
    print(json.dumps(p, indent=2))


if __name__ == "__main__":
    main()
