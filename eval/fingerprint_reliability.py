#!/usr/bin/env python3
"""
Idea 3a — SECOND CUT: topology features + reliability-weighting → the "prize gap".

The first cut (`fingerprint_ceiling.py`) computed the *attribute-layer* oracle ceiling
(perfect extraction, r=1): coarse pool 46 → attribute-optimal 13, all via `object_type`,
plateauing at 2/60 uniquely identified. This second cut closes the two gaps that cut
flagged as "next":

  1. TOPOLOGY features (Neo4j-free): derive ADJACENT_TO neighbor-class signatures +
     CONTINUOUS spanning offline from `element_index.jsonl` centroids/constraints
     (same geometry as `scripts/graph_build/02_add_topology_edges.py`, but in-memory,
     no Neo4j). Add them to the oracle fingerprint. We also *measure* FILLS / CONNECTS_TO
     from the IFC to show they are type-level homogeneous (every window fills a wall,
     every wall connects walls) → no discrimination at the granularity a photo can
     extract; the discriminative version needs a *named* neighbor (multi-hop).

  2. RELIABILITY-WEIGHTING: each feature has a real per-photo extraction reliability
     r(f) (thesis results.md U3 / Group-3). A feature used as a HARD filter recovers GT
     only with prob r(f); used wrong, it EXCLUDES GT (recall loss). Joint recall over a
     hard-filtered subset S ≈ ∏_{f∈S} r(f) (independence assumption — see caveats). This
     is exactly the recall↔discrimination tension that forces the live planner to UNION
     (soft) rather than INTERSECT (hard), which is why the realized pool is ~76, not 13.

The PRIZE GAP that P1 calibrated routing chases:
  - oracle pool (r=1, hard-filter everything, recall=100%)              = small  (ceiling)
  - reliability hard-filter pool (recall collapses to ∏r)               = unusable
  - reliability SOFT/union pool (recall protected → current system)     = large  (floor)
  - calibrated per-instance routing (hard-filter only when confidence
    says this instance is reliable)                                     = the prize

We quantify the calibration-recoverable pool and report the gap. Its size is the
**Idea-3b gate**: only train a learned feature-selector if the prize is large enough to
beat the simple confidence-threshold heuristic.

No GPU, no Neo4j, no training. IFC parse (FILLS/CONNECTS measurement) is optional.

Caveats (see docs/ROADMAP.md Idea 3a):
  - Universe deduped by GUID (852 unique; the raw index double-counts
    IfcWall/IfcWallStandardCase = 1233). The first cut's 1233 keeps duplicates; we report
    relative shrinkage, not absolute |C|, so the two cuts stay comparable in ratio.
  - r(f) values are the best-available per-field proxies (LoRA5 / Group-3 MC, n=70;
    G8 was not separately per-field tabulated). They set the *shape* of the frontier; the
    live ECE-calibration study (P1) will replace them with per-instance confidences.
  - ∏r(f) assumes per-field extraction errors are independent — an upper bound on the
    recall penalty (correlated errors would be less punishing).
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = REPO_ROOT / "data" / "references" / "element_index.jsonl"
DEFAULT_CASES = REPO_ROOT / "data" / "test_sets" / "cases_ap_heldout_e2e.jsonl"
DEFAULT_IFC = REPO_ROOT / "data" / "ifc_models" / "AdvancedProject.ifc"

# Coarse fingerprint = the live attribute pool key (storey + class).
COARSE = ("storey_name", "ifc_class")

# Per-field extraction reliability r(f) ∈ [0,1] (best-available proxy; see module caveats).
#   storey_name : 0.66  (Group-4 G8-era storey 66.1%; LoRA5 range 0.56–0.82)
#   ifc_class   : 0.50  (Group-3 MC 47.1% / Group-4 49.2% — the primary bottleneck)
#   object_type : 0.625 (Group-3 MC 62.5%)
#   material/fire_rating/is_external : 0.50 nominal (unmeasured; add ~0 oracle power anyway)
#   adjacency_sig (ADJACENT_TO) : 0.60 (thesis ADJACENT_TO predicate 60%)
#   is_continuous : 0.56 (CONTINUOUS predicate ~under-trained; conservative)
RELIABILITY = {
    "storey_name": 0.66,
    "ifc_class": 0.50,
    "object_type": 0.625,
    "material": 0.50,
    "fire_rating": 0.50,
    "is_external": 0.50,
    "adjacency_sig": 0.60,
    "is_continuous": 0.56,
}

# Attribute features (AP-usable; dead fields dropped — see first cut).
ATTR_FEATURES = ("storey_name", "ifc_class", "object_type", "material", "fire_rating", "is_external")
# Topology features derived offline (Neo4j-free).
TOPO_FEATURES = ("adjacency_sig", "is_continuous")
ALL_FEATURES = ATTR_FEATURES + TOPO_FEATURES

# Recall floor: the live system holds GT-in-pool at 100%; we report the operating point
# that keeps joint recall at or above this when hard-filtering.
RECALL_FLOOR = 0.90


def _missing(v: Any) -> bool:
    return v in (None, "", [], {}) or (isinstance(v, str) and v.strip() in ("", "None"))


def load_universe(path: Path) -> list[dict]:
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    by_guid: dict[str, dict] = {}
    for r in rows:
        by_guid[r["global_id"]] = r  # dedup (index double-counts IfcWallStandardCase)
    return list(by_guid.values())


# ── offline topology (mirrors scripts/graph_build/02_add_topology_edges.py geometry) ──

def add_topology_features(universe: list[dict], threshold: float = 1500.0, min_dist: float = 100.0) -> None:
    """Enrich each element in place with `adjacency_sig` and `is_continuous`.

    adjacency_sig = sorted tuple of distinct cross-type neighbour ifc_classes within
    `threshold` mm in the same storey (None when no neighbour → an adjacency constraint
    cannot be posed for that element). is_continuous = spans >1 storey (Top≠Base).
    """
    with_st: dict[str, list[dict]] = defaultdict(list)
    no_st: list[dict] = []
    for e in universe:
        if not e.get("centroid"):
            continue
        st = e.get("storey_name") or ""
        (with_st[st] if st else no_st).append(e)
    if no_st and with_st:  # z-band fallback for storey-less elements
        z_med = {st: sorted(x["centroid"]["z"] for x in g)[len(g) // 2] for st, g in with_st.items()}
        for e in no_st:
            with_st[min(z_med, key=lambda s: abs(z_med[s] - e["centroid"]["z"]))].append(e)

    neigh: dict[str, set] = defaultdict(set)
    for grp in with_st.values():
        for i in range(len(grp)):
            a = grp[i]; ca = a["centroid"]
            for j in range(i + 1, len(grp)):
                b = grp[j]
                if a["ifc_class"] == b["ifc_class"]:
                    continue
                cb = b["centroid"]
                d = ((ca["x"] - cb["x"]) ** 2 + (ca["y"] - cb["y"]) ** 2 + (ca["z"] - cb["z"]) ** 2) ** 0.5
                if min_dist < d <= threshold:
                    neigh[a["global_id"]].add(b["ifc_class"])
                    neigh[b["global_id"]].add(a["ifc_class"])

    for e in universe:
        s = neigh.get(e["global_id"])
        e["adjacency_sig"] = ",".join(sorted(s)) if s else None
        c = (e.get("psets") or {}).get("Constraints", {}) or {}
        base = str(c.get("Base Constraint", "")).removeprefix("Level: ").strip()
        top = str(c.get("Top Constraint", "")).removeprefix("Level: ").strip()
        e["is_continuous"] = bool(base and top and "Unconnected" not in top and base != top) or None


def confusable_count(universe: list[dict], target: dict, features: tuple[str, ...]) -> int:
    """|C(target)| = elements matching target on every feature where target has a value."""
    pred = {f: target[f] for f in features if not _missing(target.get(f))}
    return sum(1 for x in universe if all(x.get(f) == v for f, v in pred.items()))


def _med(sizes: list[float]) -> float:
    return statistics.median(sizes)


# ── reliability-weighted frontier ──

def discriminative_order(universe: list[dict], targets: list[dict], features: tuple[str, ...]) -> list[str]:
    """Order features by marginal oracle power (median |C| of coarse + that one feature,
    smallest pool = most discriminative first). Coarse keys lead."""
    extras = [f for f in features if f not in COARSE]
    power = {f: _med([confusable_count(universe, e, COARSE + (f,)) for e in targets]) for f in extras}
    return list(COARSE) + sorted(extras, key=lambda f: power[f])


def frontier(universe: list[dict], targets: list[dict], order: list[str]) -> list[dict]:
    """Greedy cumulative frontier. At each prefix S of `order` report the oracle median
    pool (r=1) and the joint recall ∏r(f) you would pay if S were hard-filtered. This is
    the recall↔discrimination tension: the pool shrinks, but ∏r collapses."""
    rows = []
    recall = 1.0
    for k in range(1, len(order) + 1):
        S = tuple(order[:k])
        f = order[k - 1]
        r = RELIABILITY.get(f, 1.0)
        recall *= r
        rows.append({
            "feature": f, "r": r, "subset": list(S),
            "oracle_pool_median": _med([confusable_count(universe, e, S) for e in targets]),
            "joint_recall_if_hard": round(recall, 3),
        })
    return rows


def analyze(universe: list[dict], targets: list[dict]) -> dict:
    coarse = [confusable_count(universe, e, COARSE) for e in targets]
    attr = [confusable_count(universe, e, ATTR_FEATURES) for e in targets]
    full = [confusable_count(universe, e, ALL_FEATURES) for e in targets]
    coarse_med, attr_med, oracle_med = _med(coarse), _med(attr), _med(full)

    order = discriminative_order(universe, targets, ALL_FEATURES)
    fr = frontier(universe, targets, order)
    full_recall = fr[-1]["joint_recall_if_hard"]          # ∏r over all features
    best_single_r = max(RELIABILITY[f] for f in order if f not in COARSE)

    # Calibrated single-feature recovery (defensible, no compounding): if the single best
    # reliable discriminator were perfectly *calibrated*, hard-filter the r(f) fraction of
    # instances it gets right and keep the rest at the coarse pool:
    #   E[|C|] = r·pool(coarse+f) + (1-r)·pool(coarse)
    extras = [f for f in order if f not in COARSE]
    calib_single = {}
    for f in extras:
        pool_with = _med([confusable_count(universe, e, COARSE + (f,)) for e in targets])
        r = RELIABILITY[f]
        calib_single[f] = round(r * pool_with + (1 - r) * coarse_med, 1)
    best_calib_feat = min(calib_single, key=lambda k: calib_single[k])

    # Can any hard filter sustain the recall floor? (With these r's: no — even storey=0.66.)
    floor_reachable = any(row["joint_recall_if_hard"] >= RECALL_FLOOR for row in fr)

    # Idea-3b gate: only train a learned feature-selector if topology features open a real
    # discrimination prize beyond attributes. Here oracle attr (13) ≈ oracle attr+topo (12)
    # → feature space is SATURATED; the recoverable gap is reliability/calibration (P1), not
    # feature selection. Gate = SKIP 3b unless full_oracle << attribute_optimal.
    feature_prize = round(attr_med - oracle_med, 1)        # what topology adds over attributes
    idea_3b_skip = feature_prize <= 2  # <=2 elements of extra shrinkage = not worth a learned selector

    return {
        "universe_size": len(universe),
        "n_targets": len(targets),
        "coarse_pool_median": coarse_med,
        "attribute_optimal_median": attr_med,
        "full_oracle_median": oracle_med,                  # attr + topology, r=1
        "full_oracle_recall_if_hard": full_recall,         # ∏r over all features
        "topology_feature_prize": feature_prize,           # attr_opt - full_oracle (≈ topology's gain)
        "best_single_reliability": best_single_r,
        "recall_floor": RECALL_FLOOR,
        "recall_floor_reachable_by_hard_filter": floor_reachable,
        "calibrated_single_feature_pool": calib_single,    # coarse + one calibrated feature
        "best_calibrated_feature": best_calib_feat,
        "best_calibrated_pool": calib_single[best_calib_feat],
        "idea_3b_gate": {
            "decision": "SKIP" if idea_3b_skip else "CONSIDER",
            "reason": (
                f"feature space saturated: attribute-oracle {attr_med} ≈ attr+topology-oracle "
                f"{oracle_med} (topology adds only {feature_prize}). The recoverable gap is "
                f"reliability-bound (best single r={best_single_r}; ∏r collapses to "
                f"{full_recall} if all hard-filtered), so the lever is P1 calibrated routing, "
                f"not a learned feature-selector."
            ) if idea_3b_skip else (
                f"topology opens {feature_prize} extra shrinkage beyond attributes — a learned "
                f"selector may be worth it."
            ),
        },
        "feature_order": order,
        "reliability": {f: RELIABILITY.get(f) for f in order},
        "frontier": fr,
    }


def measure_fills_connects(ifc_path: Path) -> dict:
    """Show FILLS/CONNECTS_TO are type-level homogeneous (no extractable-granularity
    discrimination). Optional — needs ifcopenshell + the IFC file."""
    try:
        import ifcopenshell
    except Exception as e:  # pragma: no cover - optional path
        return {"skipped": f"ifcopenshell unavailable: {e}"}
    from collections import Counter
    ifc = ifcopenshell.open(str(ifc_path))
    voids = ifc.by_type("IfcRelVoidsElement")
    fills = ifc.by_type("IfcRelFillsElement")
    conn = ifc.by_type("IfcRelConnectsPathElements")
    op2wall = {}
    for v in voids:
        op, wall = v.RelatedOpeningElement, v.RelatingBuildingElement
        if op and wall:
            op2wall[op.GlobalId] = wall.is_a()
    fill_types = Counter()
    host_types = Counter()
    for f in fills:
        op, el = f.RelatingOpeningElement, f.RelatedBuildingElement
        if op and el and op.GlobalId in op2wall:
            fill_types[el.is_a()] += 1
            host_types[op2wall[op.GlobalId]] += 1
    conn_pairs = Counter(
        (r.RelatingElement.is_a(), r.RelatedElement.is_a())
        for r in conn if r.RelatingElement and r.RelatedElement
    )
    return {
        "fills_chains": sum(fill_types.values()),
        "fills_element_types": dict(fill_types),
        "fills_host_types": dict(host_types),
        "connects_type_pairs": {f"{a}->{b}": n for (a, b), n in conn_pairs.items()},
        "note": "All windows/doors FILL walls; all CONNECTS_TO are wall<->wall → "
                "type-level predicate gives 0 discrimination; discriminative use needs a "
                "named neighbour (multi-hop, hop-2 predicate reliability ~0.05).",
    }


def make_figure(fr: list[dict], universe_n: int, out_path: Path) -> None:
    """Prize-gap figure: discrimination (oracle pool, log-y) vs the recall ∏r you pay if
    each prefix is hard-filtered. The crossing shows the reliability bind: the pool only
    shrinks as recall collapses — which is why the live planner unions (soft) and parks at
    the realized pool, far above the oracle ceiling."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    feats = [r["feature"] for r in fr]
    pools = [r["oracle_pool_median"] for r in fr]
    recall = [r["joint_recall_if_hard"] for r in fr]
    x = range(len(feats))

    fig, ax1 = plt.subplots(figsize=(8, 3.6))
    ax1.plot(x, pools, "o-", color="tab:green", label="oracle pool (r=1, hard-filter)")
    ax1.axhline(pools[-1], ls="-", color="tab:green", lw=0.6, alpha=0.4)
    ax1.set_yscale("log")
    ax1.set_ylabel("median |C(e)|  (log)")
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(feats, rotation=30, ha="right", fontsize=8)
    ax1.set_title("Idea 3a — reliability bind: discrimination vs recall")

    ax2 = ax1.twinx()
    ax2.plot(x, recall, "^-", color="tab:orange", alpha=0.8, label="joint recall ∏r (if hard)")
    ax2.axhline(RECALL_FLOOR, ls="--", color="tab:orange", lw=0.8, alpha=0.5, label=f"recall floor {RECALL_FLOOR}")
    ax2.set_ylabel("joint recall ∏r(f)", color="tab:orange")
    ax2.set_ylim(0, 1.05)

    l1, lab1 = ax1.get_legend_handles_labels()
    l2, lab2 = ax2.get_legend_handles_labels()
    ax1.legend(l1 + l2, lab1 + lab2, fontsize=7, loc="center right")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    print(f"wrote {out_path}")


def load_targets(universe: list[dict], cases_path: Optional[Path]) -> list[dict]:
    by_id = {e["global_id"]: e for e in universe}
    if cases_path and cases_path.exists():
        gts = [
            (json.loads(l).get("ground_truth") or {}).get("target_guid")
            for l in cases_path.read_text().splitlines() if l.strip()
        ]
        tgts = [by_id[g] for g in gts if g in by_id]
        if tgts:
            return tgts
    return universe


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    ap.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    ap.add_argument("--ifc", type=Path, default=DEFAULT_IFC, help="for FILLS/CONNECTS homogeneity measurement")
    ap.add_argument("--no-ifc", action="store_true", help="skip the IFC FILLS/CONNECTS measurement")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "output" / "fingerprint_reliability.json")
    ap.add_argument("--fig", type=Path, help="save the prize-gap frontier figure (PNG)")
    args = ap.parse_args()

    universe = load_universe(args.index)
    add_topology_features(universe)
    targets = load_targets(universe, args.cases)

    res = analyze(universe, targets)
    if not args.no_ifc and args.ifc.exists():
        res["fills_connects"] = measure_fills_connects(args.ifc)

    print(f"\n=== Idea 3a SECOND CUT — topology + reliability "
          f"({res['n_targets']} targets / {res['universe_size']} elements) ===")
    print(f"coarse (storey+class)        median |C| = {res['coarse_pool_median']}")
    print(f"attribute-optimal (r=1)      median |C| = {res['attribute_optimal_median']}")
    print(f"full oracle attr+topology    median |C| = {res['full_oracle_median']}"
          f"   (topology adds only {res['topology_feature_prize']}; recall if all hard = "
          f"{res['full_oracle_recall_if_hard']})")
    print(f"\nfrontier (greedy, most-discriminative-first) — discrimination vs recall:")
    print(f"  {'feature':<16}{'r(f)':<7}{'oracle|C|':<11}{'∏r recall (if hard)'}")
    print("  " + "-" * 52)
    for row in res["frontier"]:
        print(f"  {row['feature']:<16}{row['r']:<7}{row['oracle_pool_median']:<11}"
              f"{row['joint_recall_if_hard']}")
    print(f"\nrecall floor {res['recall_floor']} reachable by any hard filter? "
          f"{res['recall_floor_reachable_by_hard_filter']}  "
          f"(best single r = {res['best_single_reliability']})")
    print(f"\ncalibrated single-feature pool (coarse {res['coarse_pool_median']} + one calibrated feature):")
    for f, p in sorted(res["calibrated_single_feature_pool"].items(), key=lambda kv: kv[1]):
        print(f"   coarse + {f:<16} -> {p}")
    g = res["idea_3b_gate"]
    print(f"\nIDEA-3b GATE: {g['decision']}")
    print(f"  {g['reason']}")
    if "fills_connects" in res and "skipped" not in res["fills_connects"]:
        fc = res["fills_connects"]
        print(f"\nFILLS/CONNECTS (homogeneity): {fc['fills_chains']} FILLS {fc['fills_element_types']}; "
              f"CONNECTS {fc['connects_type_pairs']}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(res, indent=2) + "\n")
    print(f"\nwrote {args.out}")

    if args.fig:
        make_figure(res["frontier"], res["universe_size"], args.fig)


if __name__ == "__main__":
    main()
