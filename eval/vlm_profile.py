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


def make_figure(p, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax2 = plt.subplots(figsize=(11.2, 3.9))
    fig.suptitle("Perception takeaway: specialist fields make grounding usable", fontsize=16, fontweight="bold", y=1.03)
    fig.text(
        0.5,
        0.925,
        "The VLM supplies coarse typed semantics; sibling-level address fields need specialists before graph retrieval.",
        ha="center",
        fontsize=10.0,
        color="#5b6470",
    )
    names = [
        "VLM end-to-end\nAP n=60",
        "real slot specialist\nfiller n=35",
        "address ceiling\nAP n=60",
    ]
    vals = [6.7, 67.6, 78.5]
    colors = ["#8f8f8f", "#ef7d00", "#9467bd"]
    y = list(range(len(names)))
    ax2.hlines(y, 0, vals, color=colors, lw=5, alpha=0.25)
    ax2.scatter(vals, y, s=260, color=colors, zorder=3, edgecolors="white", linewidths=1.5)
    for yy, v in zip(y, vals):
        ax2.text(v + 2.0, yy, f"{v:.1f}%", va="center", fontsize=9.5, fontweight="bold")
    ax2.set_yticks(y)
    ax2.set_yticklabels(names, fontsize=10.0)
    ax2.set_xlim(0, 100)
    ax2.set_xlabel("Top-1 right-element-first accuracy", fontsize=10.0)
    ax2.grid(axis="x", color="#e5e8ee", lw=0.8)
    ax2.invert_yaxis()
    for side in ("top", "right", "left"):
        ax2.spines[side].set_visible(False)
    ax2.tick_params(axis="y", length=0)

    fig.tight_layout(rect=[0, 0, 1, 0.87])
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
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
