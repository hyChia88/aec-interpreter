"""M2a — wall-fingerprint harness: floor / oracle baselines + per-field oracle ablations.

The wall spatial address (RQ1) is the tuple
    (connection_degree, hosted_opening_count, length_band, is_external)
recovered from `wall_fingerprint.py`. Before building the CV detector (M2b), diagnose WHICH
field is the realizable lever — exactly as M1a (`slot_extractor_m1.py`) did for the position
slot (i vs M). Mirrors that harness: a predictor maps case → (fingerprint dict, confidence);
intrinsic per-field accuracy + a downstream that feeds the predicted address tuple as the
search key and scores filler/wall Top-k with NO self-match artefact (a candidate scores on the
address only if ITS OWN true tuple equals the prediction).

Scored against the same exact-tuple match the oracle ceiling uses (oracle reproduces wall
Top-1 64.2). Run:  .venv/bin/python eval/wall_extractor_m1.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Callable, Optional

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
from rerank_prize import (load_index, load_cases, pool_candidates, cand_feats,
                          _rank_stats, _topk, DEFAULT_INDEX, DEFAULT_TRACES)
from reconstruct_position_index import load_position_index
from wall_fingerprint import load_wall_fingerprint, wall_address
from spatial_address_ceiling import subgroup, DEFAULT_POS, DEFAULT_WALL

WALLFP = load_wall_fingerprint(DEFAULT_WALL)
FIELDS = ("connection_degree", "hosted_opening_count", "length_band", "is_external")
Pred = tuple[Optional[dict], float]   # (fingerprint dict or None, confidence)


def gt_fp(case) -> Optional[dict]:
    return WALLFP.get(case["scenario"]["ground_truth"]["target_guid"])


def wall_cases(cases, pos) -> list:
    return [c for c in cases
            if subgroup(c["scenario"]["ground_truth"]["target_guid"], pos, WALLFP) == "wall"]


def addr_of(fp: Optional[dict]) -> Optional[tuple]:
    return wall_address(fp) if fp else None


# ── predictors ───────────────────────────────────────────────────────────────
def make_prior(walls) -> Callable:
    modal = {f: Counter(gt_fp(c).get(f) for c in walls).most_common(1)[0][0] for f in FIELDS}

    def f(case) -> Pred:
        return (dict(modal), 0.1)
    return f


def oracle_full(case) -> Pred:
    fp = gt_fp(case)
    return (dict(fp), 1.0) if fp else (None, 0.0)


def make_oracle_field(walls, field) -> Callable:
    """Recover ONLY `field` perfectly; the rest stay at the modal prior. Isolates that field's
    realizable lift over the floor (the wall analogue of oracle-i / oracle-M)."""
    modal = {f: Counter(gt_fp(c).get(f) for c in walls).most_common(1)[0][0] for f in FIELDS}

    def f(case) -> Pred:
        fp = gt_fp(case)
        if not fp:
            return (None, 0.0)
        out = dict(modal); out[field] = fp.get(field)
        return (out, 0.5)
    return f


def make_oracle_drop(walls, field) -> Callable:
    """Recover everything EXCEPT `field` (that one stays modal). Isolates how *necessary* the
    field is — a large Top-1 drop vs oracle_full means the field is load-bearing."""
    modal = {f: Counter(gt_fp(c).get(f) for c in walls).most_common(1)[0][0] for f in FIELDS}

    def f(case) -> Pred:
        fp = gt_fp(case)
        if not fp:
            return (None, 0.0)
        out = dict(fp); out[field] = modal[field]
        return (out, 0.5)
    return f


# ── evaluation ───────────────────────────────────────────────────────────────
def intrinsic(pred: Callable, walls) -> dict:
    n = len(walls)
    cov = 0
    hit = {f: 0 for f in FIELDS}
    exact = 0
    for c in walls:
        fp, _ = pred(c)
        if fp is None:
            continue
        cov += 1
        g = gt_fp(c)
        for f in FIELDS:
            hit[f] += (fp.get(f) == g.get(f))
        exact += (addr_of(fp) == addr_of(g))
    out = {"coverage": cov / n, "exact_tuple": exact / n}
    out.update({f: hit[f] / n for f in FIELDS})
    return out


def downstream(pred: Callable, walls, idx, pos) -> dict:
    """Feed the predicted wall-address tuple as the search key → Top-1/Top-10. A candidate
    scores +1 on the address only if ITS OWN true wall_address equals the prediction (no
    self-match). storey + class each contribute +1, as in the M1a harness."""
    t1 = t10 = 0.0
    n = 0
    for c in walls:
        gt = c["scenario"]["ground_truth"]["target_guid"]
        pool = pool_candidates(c)
        if gt not in pool:
            continue
        n += 1
        fp, _ = pred(c)
        key = addr_of(fp)
        gf = cand_feats(gt, pool[gt], idx, pos)
        scores = {}
        for guid, tc in pool.items():
            cf = cand_feats(guid, tc, idx, pos)
            s = float(cf.get("storey") == gf.get("storey")) + float(cf.get("ifc_class") == gf.get("ifc_class"))
            if key is not None and addr_of(WALLFP.get(guid)) == key:
                s += 1.0
            scores[guid] = s
        h, t = _rank_stats(scores, gt)
        t1 += _topk(h, t, 1); t10 += _topk(h, t, 10)
    return {"n": n, "top1": 100 * t1 / n, "top10": 100 * t10 / n}


def run(idx, cases, pos) -> dict:
    walls = wall_cases(cases, pos)
    preds = {"prior (modal fp) — FLOOR": make_prior(walls),
             "oracle full — CEILING": oracle_full}
    for fld in FIELDS:
        preds[f"oracle {fld} only"] = make_oracle_field(walls, fld)
    for fld in FIELDS:
        preds[f"oracle drop {fld}"] = make_oracle_drop(walls, fld)
    out = {"n_walls": len(walls), "rows": {}}
    for name, p in preds.items():
        out["rows"][name] = {**intrinsic(p, walls), **downstream(p, walls, idx, pos)}
    return out


def main():
    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    r = run(idx, cases, pos)
    print(f"=== M2a wall harness — {r['n_walls']} wall targets ===\n")
    print(f"{'predictor':<28}{'cov':>5}{'tuple':>7}{'cd':>6}{'hoc':>6}{'len':>6}{'ext':>6}{'Top-1':>8}{'Top-10':>8}")
    for name, m in r["rows"].items():
        print(f"{name:<28}{m['coverage']*100:>4.0f}%{m['exact_tuple']*100:>6.0f}%"
              f"{m['connection_degree']*100:>5.0f}%{m['hosted_opening_count']*100:>5.0f}%"
              f"{m['length_band']*100:>5.0f}%{m['is_external']*100:>5.0f}%"
              f"{m['top1']:>8.1f}{m['top10']:>8.1f}")


if __name__ == "__main__":
    main()
