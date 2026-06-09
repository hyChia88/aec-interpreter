"""
Regression guard: the offline `--from-traces` scorer must keep reproducing the
frozen thesis Track-B numbers. If a change to run_benchmark's scoring drifts the
baseline, this fails.

- G8 (thesis canonical) must match ALL metrics exactly (the harness-validation gate).
- Gemini must match all RANKING metrics exactly; its gt_in_pool is a documented
  reference-side known-diff (this repo's cleaner union-of-pool definition gives 95.0%
  vs the legacy 91.7%) — asserted as such so the divergence stays intentional.
"""
import json
from pathlib import Path

import pytest

import run_benchmark as rb

REPO_ROOT = Path(__file__).resolve().parent.parent
FIX = REPO_ROOT / "eval" / "fixtures"
NBOOT = 200  # point estimates are exact regardless of N; keep small for speed


def _agg(variant: str) -> dict:
    rows = [
        json.loads(l)
        for l in (FIX / "traces" / f"{variant}.jsonl").read_text().splitlines()
        if l.strip()
    ]
    cases = [rb.score_case(r) for r in rows]
    return rb.aggregate(cases, n_boot=NBOOT, seed=0)


def test_g8_full_parity():
    """G8: every metric matches the frozen thesis JSON within tolerance."""
    agg = _agg("g8_posctx_dim")
    assert agg["n"] == 60
    rows = rb.parity_check(agg, FIX / "metrics" / "g8_posctx_dim.json")
    mismatches = [(name, got, exp) for name, got, exp, ok in rows if not ok]
    assert not mismatches, f"G8 parity drift: {mismatches}"


def test_g8_headline_values():
    """Pin the exact headline numbers we report in the paper."""
    agg = _agg("g8_posctx_dim")
    assert agg["gt_in_pool"]["pct"] == 100.0
    assert agg["top1"]["pct"] == 6.7
    assert agg["top10"]["pct"] == 30.0
    assert agg["mrr"]["value"] == 0.1104
    assert agg["final_pool"]["median"] == 76.0
    assert agg["final_pool"]["mean"] == 118.4


def test_gemini_ranking_parity_and_known_gt_in_pool_diff():
    """Gemini: ranking metrics exact; gt_in_pool intentionally diverges (cleaner def)."""
    agg = _agg("gemini_ap_v2")
    rows = rb.parity_check(agg, FIX / "metrics" / "gemini_ap_v2.json")
    by_name = {name: (got, exp, ok) for name, got, exp, ok in rows}
    # all non-gt_in_pool metrics must match
    for name, (got, exp, ok) in by_name.items():
        if name == "gt_in_pool %":
            continue
        assert ok, f"gemini ranking drift on {name}: got {got}, exp {exp}"
    # documented known-diff: clean union-of-pool definition
    got, exp, ok = by_name["gt_in_pool %"]
    assert got == 95.0 and exp == 91.7 and not ok, (
        f"gemini gt_in_pool known-diff changed: got {got}, exp {exp} "
        "(update docs/results_ledger.md if this is intentional)"
    )


def test_top1_ci_is_wide_at_n60():
    """Sanity: bootstrap CI for Top-1 is wide at n=60 (justifies demoting Top-1)."""
    agg = _agg("g8_posctx_dim")
    lo, hi = agg["top1"]["ci95"]
    assert (hi - lo) > 8.0, "expected a wide Top-1 CI at n=60"
