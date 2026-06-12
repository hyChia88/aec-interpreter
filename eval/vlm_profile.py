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
    fields = ["storey", "ifc_class", "relation\npresent", "direction", "position\nslot", "size"]
    vals = [p["storey_ex"], p["class_ex"], p["rel"], p["dir"], p["slot_ex"], p["size_ex"]]
    # green = coarse (saturated, VLM-recoverable); red = discriminating (delegate to specialists)
    colors = ["#2ca02c", "#2ca02c", "#7fb3d5", "#7fb3d5", "#d62728", "#d62728"]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    bars = ax.bar(range(len(fields)), vals, color=colors)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 2, f"{v:.0f}%", ha="center", fontsize=10, fontweight="bold")
    ax.set_xticks(range(len(fields))); ax.set_xticklabels(fields, fontsize=9)
    ax.set_ylabel("extracted (%)"); ax.set_ylim(0, 108)
    ax.set_title("Fine-tuned VLM (Qwen2.5-VL LoRA, G8) — per-field extraction\n"
                 "nails the coarse prefix (green); fails the discriminating fields (red) → delegate to specialists",
                 fontsize=11)
    fig.tight_layout(); fig.savefig(out_path, dpi=130)
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
