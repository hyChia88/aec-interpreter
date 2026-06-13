#!/usr/bin/env python3
"""
Single benchmark entrypoint for the AEC Interpreter.

Two modes (see docs/ROADMAP.md, Phase 0):

  --from-traces : score saved per-case end-to-end trace JSONL **offline**.
                  No Neo4j, no GPU. Used for harness validation, thesis parity,
                  and as a fast regression baseline over frozen traces.

  --live        : run the real symbolic pipeline (plan -> retrieve -> rank) against a
                  live Neo4j graph, using the frozen G8 extraction as precomputed
                  constraints (no GPU/VLM). Proves the in-repo graph build + planner
                  reconstruct the frozen retrieval. GT-in-pool + pool sizes reproduce
                  exactly; Top-k order needs the Gemini rerank (GOOGLE_API_KEY) to match.
                  See eval/live_runner.py.

Retrieval (Track B) metrics, every rate reported with a bootstrap 95% CI:
  GT-in-pool (over the FULL retrieved pool), Top-1, Top-5, Top-10, MRR@10,
  final-pool size (mean + median), initial-pool size (mean + median),
  search-space reduction.

Clean, documented definitions (independent re-implementation; cross-checked
against the frozen thesis metrics via --reference):
  GT          = scenario.ground_truth.target_guid
  shortlist   = interpreter_output.candidates           (ranked, <=10) -> Top-k, MRR
  full pool   = union of internals.retrieval_results[*].candidates[*].guid -> GT-in-pool
  final size  = row.final_pool_size ; initial size = row.initial_pool_size
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXPERIMENTS = REPO_ROOT / "eval" / "experiments.yaml"


# ──────────────────────────────────────────────────────────────────────────────
# per-case scoring
# ──────────────────────────────────────────────────────────────────────────────
def _gt_guid(row: dict) -> Optional[str]:
    return ((row.get("scenario") or {}).get("ground_truth") or {}).get("target_guid")


def _shortlist_guids(row: dict) -> list[str]:
    cands = (row.get("interpreter_output") or {}).get("candidates") or []
    return [c.get("guid") for c in cands if isinstance(c, dict)]


def _full_pool_guids(row: dict) -> set[str]:
    guids: set[str] = set()
    for res in (row.get("internals") or {}).get("retrieval_results") or []:
        for c in res.get("candidates") or []:
            if isinstance(c, dict) and c.get("guid"):
                guids.add(c["guid"])
    return guids


def score_case(row: dict) -> dict[str, Any]:
    """Per-case scored record. rank is 1-based index of GT in the shortlist (None if absent)."""
    gt = _gt_guid(row)
    shortlist = _shortlist_guids(row)
    rank: Optional[int] = None
    if gt and gt in shortlist:
        rank = shortlist.index(gt) + 1

    final_pool = row.get("final_pool_size")
    initial_pool = row.get("initial_pool_size")
    return {
        "case_id": row.get("scenario_id") or row.get("case_id"),
        "rank": rank,
        "gt_in_pool": bool(gt and gt in _full_pool_guids(row)),
        "top1": rank == 1,
        "top5": rank is not None and rank <= 5,
        "top10": rank is not None and rank <= 10,
        "recip_rank": (1.0 / rank) if rank is not None else 0.0,
        "final_pool": int(final_pool) if final_pool else None,
        "initial_pool": int(initial_pool) if initial_pool else None,
    }


# ──────────────────────────────────────────────────────────────────────────────
# bootstrap CIs
# ──────────────────────────────────────────────────────────────────────────────
def bootstrap_ci(
    values: list[float],
    stat: Callable[[np.ndarray], np.ndarray],
    n_boot: int,
    seed: int,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """Return (point_estimate, ci_low, ci_high). `stat` reduces along axis=1."""
    arr = np.asarray(values, dtype=float)
    n = len(arr)
    if n == 0:
        return 0.0, 0.0, 0.0
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    boot = stat(arr[idx])
    lo, hi = np.percentile(boot, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    point = float(stat(arr.reshape(1, -1))[0])
    return point, float(lo), float(hi)


def _mean(a: np.ndarray) -> np.ndarray:
    return a.mean(axis=1)


def _median(a: np.ndarray) -> np.ndarray:
    return np.median(a, axis=1)


# ──────────────────────────────────────────────────────────────────────────────
# aggregate
# ──────────────────────────────────────────────────────────────────────────────
def aggregate(cases: list[dict], n_boot: int, seed: int) -> dict[str, Any]:
    n = len(cases)
    finals = [c["final_pool"] for c in cases if c["final_pool"] is not None]
    initials = [c["initial_pool"] for c in cases if c["initial_pool"] is not None]

    def rate(key: str) -> dict[str, float]:
        pt, lo, hi = bootstrap_ci([1.0 if c[key] else 0.0 for c in cases], _mean, n_boot, seed)
        return {"pct": round(100 * pt, 1), "ci95": [round(100 * lo, 1), round(100 * hi, 1)],
                "count": int(round(pt * n))}

    mrr_pt, mrr_lo, mrr_hi = bootstrap_ci([c["recip_rank"] for c in cases], _mean, n_boot, seed)
    fp_mean = bootstrap_ci(finals, _mean, n_boot, seed) if finals else (0, 0, 0)
    fp_med = bootstrap_ci(finals, _median, n_boot, seed) if finals else (0, 0, 0)
    ip_mean = bootstrap_ci(initials, _mean, n_boot, seed) if initials else (0, 0, 0)
    reductions = [
        1.0 - c["final_pool"] / c["initial_pool"]
        for c in cases
        if c["final_pool"] and c["initial_pool"]
    ]
    red_pt, red_lo, red_hi = bootstrap_ci(reductions, _mean, n_boot, seed) if reductions else (0, 0, 0)

    return {
        "n": n,
        "n_boot": n_boot,
        "seed": seed,
        "gt_in_pool": rate("gt_in_pool"),
        "top1": rate("top1"),
        "top5": rate("top5"),
        "top10": rate("top10"),
        "mrr": {"value": round(mrr_pt, 4), "ci95": [round(mrr_lo, 4), round(mrr_hi, 4)]},
        "final_pool": {
            "mean": round(fp_mean[0], 1), "mean_ci95": [round(fp_mean[1], 1), round(fp_mean[2], 1)],
            "median": round(fp_med[0], 1), "median_ci95": [round(fp_med[1], 1), round(fp_med[2], 1)],
        },
        "initial_pool": {"mean": round(ip_mean[0], 1)},
        "search_space_reduction": {
            "mean": round(red_pt, 4), "ci95": [round(red_lo, 4), round(red_hi, 4)]
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# parity check vs frozen thesis metrics
# ──────────────────────────────────────────────────────────────────────────────
def parity_check(agg: dict, ref_path: Path) -> list[tuple[str, float, float, bool]]:
    ref = json.loads(ref_path.read_text())
    o = ref.get("overall", {})
    ps = ref.get("pool_stats", {})
    checks = [
        ("gt_in_pool %", agg["gt_in_pool"]["pct"], o.get("gt_in_pct"), 0.1),
        ("top1 %", agg["top1"]["pct"], o.get("top1_pct"), 0.1),
        ("top5 %", agg["top5"]["pct"], o.get("top5_pct"), 0.1),
        ("top10 %", agg["top10"]["pct"], o.get("top10_pct"), 0.1),
        ("mrr", agg["mrr"]["value"], o.get("mrr"), 0.001),
        ("final pool mean", agg["final_pool"]["mean"], o.get("avg_pool"), 0.1),
    ]
    if ps.get("median_final_pool") is not None:
        checks.append(("final pool median", agg["final_pool"]["median"], ps["median_final_pool"], 0.5))
    rows = []
    for name, got, exp, tol in checks:
        ok = exp is not None and abs(got - exp) <= tol
        rows.append((name, got, exp, ok))
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# reporting
# ──────────────────────────────────────────────────────────────────────────────
def print_report(name: str, agg: dict, parity: Optional[list]) -> bool:
    print(f"\n=== Benchmark: {name}  (n={agg['n']}, bootstrap={agg['n_boot']}, seed={agg['seed']}) ===")
    print(f"{'metric':<22}{'estimate':<14}{'95% CI':<22}")
    print("-" * 58)
    for key, label in [("gt_in_pool", "GT-in-pool"), ("top1", "Top-1"),
                       ("top5", "Top-5"), ("top10", "Top-10")]:
        m = agg[key]
        print(f"{label:<22}{str(m['pct'])+'%':<14}[{m['ci95'][0]}, {m['ci95'][1]}]")
    mrr = agg["mrr"]
    print(f"{'MRR@10':<22}{mrr['value']:<14}[{mrr['ci95'][0]}, {mrr['ci95'][1]}]")
    fp = agg["final_pool"]
    print(f"{'final pool (mean)':<22}{str(fp['mean']):<14}[{fp['mean_ci95'][0]}, {fp['mean_ci95'][1]}]")
    print(f"{'final pool (median)':<22}{str(fp['median']):<14}[{fp['median_ci95'][0]}, {fp['median_ci95'][1]}]")
    print(f"{'search-space reduc.':<22}{agg['search_space_reduction']['mean']}")

    all_ok = True
    if parity is not None:
        print(f"\n--- Parity vs frozen thesis metrics ---")
        print(f"{'metric':<22}{'computed':<12}{'reference':<12}{'match'}")
        print("-" * 54)
        for nm, got, exp, ok in parity:
            all_ok = all_ok and ok
            print(f"{nm:<22}{str(got):<12}{str(exp):<12}{'✓' if ok else '✗ MISMATCH'}")
        print(f"\nPARITY: {'PASS ✅' if all_ok else 'FAIL ❌'}")
    return all_ok


def ledger_row(name: str, agg: dict) -> str:
    fp = agg["final_pool"]
    return (
        f"| _(fill date)_ | Phase 0 | from-traces | _(commit)_ | AP held-out ({agg['n']}) | "
        f"Top-10 / MRR / med-pool | "
        f"{agg['top10']['pct']}% / {agg['mrr']['value']} / {fp['median']} | "
        f"Top-10 [{agg['top10']['ci95'][0]},{agg['top10']['ci95'][1]}] | confirmatory | "
        f"`{name}` offline parity |"
    )


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────
def resolve_variant(variant: str, experiments: Path) -> tuple[Path, Optional[Path], str]:
    cfg = yaml.safe_load(experiments.read_text())
    v = (cfg.get("variants") or {}).get(variant)
    if not v:
        sys.exit(f"variant '{variant}' not found in {experiments}")
    trace = REPO_ROOT / v["trace"]
    ref = REPO_ROOT / v["reference"] if v.get("reference") else None
    return trace, ref, v.get("display_name", variant)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--from-traces", type=Path, metavar="TRACE.jsonl",
                      help="score a saved e2e trace JSONL offline")
    mode.add_argument("--variant", help="named variant from experiments.yaml (offline)")
    mode.add_argument("--live", action="store_true",
                      help="run the real symbolic pipeline against live Neo4j (precomputed extraction)")
    ap.add_argument("--p0-strategy", dest="p0_strategy", default="p0_union_p1",
                    help="P0 retrieval strategy for --live (default p0_union_p1, the paper-canonical union)")
    ap.add_argument("--reference", type=Path, help="frozen *_metrics.json for parity check")
    ap.add_argument("--name", help="label for the run (default: trace/variant name)")
    ap.add_argument("--experiments", type=Path, default=DEFAULT_EXPERIMENTS)
    ap.add_argument("--bootstrap", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, help="write computed metrics JSON here")
    ap.add_argument("--ledger", action="store_true", help="also print a results_ledger.md row")
    args = ap.parse_args()

    if args.live:
        # Live retrieval reproduction: plan -> retrieve -> rank against a running Neo4j,
        # using the frozen G8 extraction as precomputed constraints (no GPU/VLM). Proves
        # the in-repo graph build + planner reconstruct the frozen pipeline's retrieval.
        # GT-in-pool + pool sizes reproduce exactly; Top-k may differ (Gemini rerank not in
        # the offline live path). See eval/live_runner.py.
        from live_runner import run_live
        name = args.name or "live"
        rows = run_live(args.p0_strategy)
        cases = [score_case(r) for r in rows]
        agg = aggregate(cases, args.bootstrap, args.seed)
        ref_path = args.reference
        parity = parity_check(agg, ref_path) if ref_path else None
        ok = print_report(name, agg, parity)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps({"name": name, "mode": "live", **agg}, indent=2))
            print(f"\nwrote {args.out}")
        sys.exit(0 if (parity is None or ok) else 1)

    if args.variant:
        trace_path, ref_path, name = resolve_variant(args.variant, args.experiments)
        ref_path = args.reference or ref_path
    else:
        trace_path, ref_path, name = args.from_traces, args.reference, args.name or args.from_traces.stem
    name = args.name or name

    rows = [json.loads(l) for l in trace_path.read_text().splitlines() if l.strip()]
    cases = [score_case(r) for r in rows]
    agg = aggregate(cases, args.bootstrap, args.seed)

    parity = parity_check(agg, ref_path) if ref_path else None
    ok = print_report(name, agg, parity)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"name": name, "trace": str(trace_path), **agg}, indent=2))
        print(f"\nwrote {args.out}")
    if args.ledger:
        print("\nresults_ledger.md row:\n" + ledger_row(name, agg))

    sys.exit(0 if (parity is None or ok) else 1)


if __name__ == "__main__":
    main()
