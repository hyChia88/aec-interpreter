"""Triage effort — does the system actually change the coordinator's work? (value-prop measure)

The plan asks for a small triage time/success measurement so the contribution is grounded in a
practical payoff, not only retrieval metrics. We use a transparent, fully data-derived proxy:

  triage effort = the expected number of candidate elements a coordinator must inspect (in the
  model) to reach the correct one = the GT's expected rank under each method's ordering of the
  SAME retrieved pool (h strictly-above + (t tied + 1)/2, i.e. uniform random tie-break).

  - unranked final pool: no ranking — inspect the retrieved pool in arbitrary order
                         → (|pool|+1)/2
  - coarse storey+class: rank by the ontological prefix only (what a class/floor filter gives)
  - + spatial address  : rank by the type-conditional address (oracle)

Reported with success@k (worker checks the top-k) and a time framing (effort × a per-inspection
constant). Honest: this is an effort *proxy* from the rankings, not a human user study.

Run:  .venv/bin/python eval/triage_effort.py   →  output/triage_effort.{png,json} + ledger row.
"""
from __future__ import annotations

import json
import statistics as st
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
from rerank_prize import (load_index, load_cases, pool_candidates, _rank_stats, _topk,
                          DEFAULT_INDEX, DEFAULT_TRACES)
from reconstruct_position_index import load_position_index
from wall_fingerprint import load_wall_fingerprint
from spatial_address_ceiling import score, DEFAULT_POS, DEFAULT_WALL

REPO = EVAL.parent
OUT = REPO / "output"
SEC_PER_INSPECT = 15        # assumed seconds to locate + visually verify one element in the model


def inspections(h: int, t: int) -> float:
    return h + (t + 1) / 2.0


def main():
    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    wallfp = load_wall_fingerprint(DEFAULT_WALL)

    arms = {"unranked final pool": {"storey": 0.0},                # uniform → all tied
            "coarse (storey+class)": {"storey": 1.0, "ifc_class": 1.0},
            "+ spatial address": {"storey": 1.0, "ifc_class": 1.0, "spatial_address": 1.0}}
    eff = {a: [] for a in arms}
    succ = {a: {1: 0, 5: 0, 10: 0} for a in arms}
    n = 0
    for c in cases:
        gt = c["scenario"]["ground_truth"]["target_guid"]
        pool = pool_candidates(c)
        if gt not in pool:
            continue
        n += 1
        for a, w in arms.items():
            sc = score(pool, idx, pos, wallfp, gt, w) if w else {g: 0.0 for g in pool}
            h, t = _rank_stats(sc, gt)
            eff[a].append(inspections(h, t))
            for k in (1, 5, 10):
                succ[a][k] += _topk(h, t, k)         # P(GT in top-k) under random tie-break

    rows = {}
    for a in arms:
        rows[a] = {"n": n, "median_inspections": st.median(eff[a]), "mean_inspections": st.mean(eff[a]),
                   "median_seconds": st.median(eff[a]) * SEC_PER_INSPECT,
                   **{f"success@{k}": 100 * succ[a][k] / n for k in (1, 5, 10)}}

    base = rows["unranked final pool"]["median_inspections"]
    addr = rows["+ spatial address"]["median_inspections"]

    OUT.mkdir(exist_ok=True)
    json.dump(rows, open(OUT / "triage_effort.json", "w"), indent=2)
    _figure(rows)
    print(f"\n{'arm':<24}{'med.insp':>9}{'mean':>7}{'~sec':>7}{'succ@1':>8}{'@5':>7}{'@10':>7}")
    for a, m in rows.items():
        print(f"{a:<24}{m['median_inspections']:>9.1f}{m['mean_inspections']:>7.1f}{m['median_seconds']:>7.0f}"
              f"{m['success@1']:>8.1f}{m['success@5']:>7.1f}{m['success@10']:>7.1f}")
    print(f"\nunranked final pool → address: median inspections {base:.0f} → {addr:.1f}  "
          f"({base/addr:.0f}× less effort); ~{base*SEC_PER_INSPECT:.0f}s → ~{addr*SEC_PER_INSPECT:.0f}s per element "
          f"(at {SEC_PER_INSPECT}s/inspection).")


def _figure(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = list(rows); med = [rows[a]["median_inspections"] for a in names]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    bars = ax.bar(range(len(names)), med, color=["#bbb", "#7fb3d5", "#9467bd"])
    for b, v in zip(bars, med):
        ax.text(b.get_x() + b.get_width() / 2, v + max(med) * 0.02, f"{v:.0f}",
                ha="center", fontsize=11, fontweight="bold")
    ax.set_xticks(range(len(names))); ax.set_xticklabels(names, fontsize=10)
    ax.set_ylabel("median inspections to find the element")
    ax.set_title("Triage effort — pool review shifts from search to verification\n"
                 f"unranked pool {med[0]:.0f} → spatial address {med[-1]:.0f} candidate inspections per element", fontsize=11)
    fig.tight_layout(); fig.savefig(OUT / "triage_effort.png", dpi=130)
    print("figure →", OUT / "triage_effort.png")


if __name__ == "__main__":
    main()
