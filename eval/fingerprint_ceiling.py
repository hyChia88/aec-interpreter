#!/usr/bin/env python3
"""
Idea 3a — offline optimal-fingerprint ceiling (FIRST CUT: attribute-layer, Neo4j-free).

Reframes element grounding as **constrained discriminative feature-selection**: for a
target element e, the confusable set C(e) = elements sharing e's coarse fingerprint
(storey + ifc_class — the live "attribute pool"). Each extra discriminative feature
shrinks C(e). This script computes the *oracle* (reliability = 1) attribute-only ceiling:
how small does the pool get using only attribute features a specialist could plausibly
extract — BEFORE any topology.

This first cut needs no GPU, no Neo4j, no training — pure compute over
`data/references/element_index.jsonl`. The topology-feature cut + reliability-weighting
(= P1 generalized per-subset) come next.

Caveats (see docs/ROADMAP.md Idea 3a):
  - Universe here = element_index (1233 AP elements); the live graph had 1666 + finer
    ifc_class granularity, so absolute |C| differs from the live pool ~76. The RELATIVE
    coarse→attribute-optimal shrinkage is the result, not the absolute number.
  - Oracle (r=1): upper bound "given perfect extraction". Reliability-weighting is the next cut.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = REPO_ROOT / "data" / "references" / "element_index.jsonl"
DEFAULT_CASES = REPO_ROOT / "data" / "test_sets" / "cases_ap_heldout_e2e.jsonl"

# Coarse fingerprint = the live attribute pool key.
COARSE = ("storey_name", "ifc_class")
# Attribute features a specialist could plausibly extract (AP-usable; dead fields dropped).
# space_name / target_name_keyword (0% coverage) and neighbor_type (7%) excluded for AP.
ATTR_FEATURES = ("storey_name", "ifc_class", "object_type", "material", "fire_rating", "is_external")


def _missing(v: Any) -> bool:
    return v in (None, "", [], {}) or (isinstance(v, str) and v.strip() in ("", "None"))


def load_universe(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def confusable_count(universe: list[dict], target: dict, features: tuple[str, ...]) -> int:
    """|C(target)| = elements matching target on every feature where target has a value."""
    pred = {f: target[f] for f in features if not _missing(target.get(f))}
    return sum(1 for x in universe if all(x.get(f) == v for f, v in pred.items()))


def _dist(sizes: list[int]) -> dict:
    s = sorted(sizes)
    return {
        "n": len(s),
        "median": statistics.median(s),
        "mean": round(statistics.mean(s), 1),
        "min": s[0],
        "max": s[-1],
        "p25": s[len(s) // 4],
        "p75": s[(3 * len(s)) // 4],
    }


def analyze(universe: list[dict], targets: list[dict]) -> dict:
    coarse = [confusable_count(universe, e, COARSE) for e in targets]
    attr_opt = [confusable_count(universe, e, ATTR_FEATURES) for e in targets]
    shrink = [c / a for c, a in zip(coarse, attr_opt) if a]
    unique = sum(1 for a in attr_opt if a == 1)

    # marginal power: median |C| of coarse + each single extra feature
    marginal = {}
    extras = [f for f in ATTR_FEATURES if f not in COARSE]
    for f in extras:
        feats = COARSE + (f,)
        marginal[f] = _dist([confusable_count(universe, e, feats) for e in targets])["median"]

    return {
        "universe_size": len(universe),
        "coarse_pool": _dist(coarse),
        "attribute_optimal_pool": _dist(attr_opt),
        "median_shrinkage_x": round(statistics.median(shrink), 2) if shrink else None,
        "targets_uniquely_identified_by_attributes": f"{unique}/{len(targets)}",
        "coarse_key": list(COARSE),
        "attr_features": list(ATTR_FEATURES),
        "marginal_median_pool_coarse_plus": marginal,
    }


def make_figure(coarse: list[int], attr: list[int], out_path: Path, scope: str) -> None:
    """Spine figure (§4): coarse vs attribute-optimal pool-size distributions (log-x)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.boxplot([coarse, attr], vert=False, labels=["coarse\n(storey+class)", "attribute-\noptimal (r=1)"],
               widths=0.6, showfliers=False)
    for i, data in enumerate([coarse, attr], start=1):
        ax.scatter(data, [i] * len(data), alpha=0.25, s=12, color="tab:blue")
    ax.axvline(9, ls="--", color="tab:green", lw=1, label="oracle-L3 ≈9 (needs topology, live graph)")
    ax.set_xscale("log")
    ax.set_xlabel("confusable-set size |C(e)|  (log)")
    ax.set_title(f"Attribute-layer fingerprint ceiling — {scope}")
    ax.legend(fontsize=8, loc="lower right")
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
    return universe  # fall back to building-wide


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    ap.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="held-out cases (targets); omit for building-wide")
    ap.add_argument("--building-wide", action="store_true", help="use all elements as targets")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "output" / "fingerprint_ceiling.json")
    ap.add_argument("--fig", type=Path, help="save the spine figure (PNG)")
    args = ap.parse_args()

    universe = load_universe(args.index)
    targets = universe if args.building_wide else load_targets(universe, args.cases)
    scope = "building-wide" if (args.building_wide or targets is universe) else "held-out targets"

    res = analyze(universe, targets)
    res["scope"] = scope

    print(f"\n=== Idea 3a — attribute-layer fingerprint ceiling ({scope}, "
          f"{res['coarse_pool']['n']} targets / {res['universe_size']} elements) ===")
    cp, ap_ = res["coarse_pool"], res["attribute_optimal_pool"]
    print(f"{'pool':<26}{'median':<9}{'mean':<9}{'min..max':<12}{'p25..p75'}")
    print("-" * 60)
    for label, d in [("coarse (storey+class)", cp), ("attribute-optimal (r=1)", ap_)]:
        rng = f"{d['min']}..{d['max']}"
        print(f"{label:<26}{d['median']:<9}{d['mean']:<9}{rng:<12}{d['p25']}..{d['p75']}")
    print(f"\nmedian shrinkage coarse->attr-optimal: {res['median_shrinkage_x']}x")
    print(f"uniquely id'd by attributes alone: {res['targets_uniquely_identified_by_attributes']}")
    print("\nmarginal power (median |C| of coarse + one feature):")
    for f, m in sorted(res["marginal_median_pool_coarse_plus"].items(), key=lambda kv: kv[1]):
        print(f"   + {f:<16} -> {m}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(res, indent=2) + "\n")
    print(f"\nwrote {args.out}")

    if args.fig:
        coarse = [confusable_count(universe, e, COARSE) for e in targets]
        attr = [confusable_count(universe, e, ATTR_FEATURES) for e in targets]
        make_figure(coarse, attr, args.fig, scope)


if __name__ == "__main__":
    main()
