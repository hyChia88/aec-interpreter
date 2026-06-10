#!/usr/bin/env python3
"""
Idea 3c — visual-topological spatial address ceiling (first cut; offline, Neo4j-free).

Unifies the two element-class-specific spatial addresses into one type-conditional
descriptor and measures its oracle Top-k/MRR prize on the real G8 pools:

  - window/door fillers  -> `position_context` slot   (reconstruct_position_index.py)
  - walls / non-filler   -> wall fingerprint           (wall_fingerprint.py:
                            connection_degree, hosted_opening_count, length_band, is_external)

This answers the open piece of the spatial-address contribution: cut-3 showed the
position-slot solves Top-1 for the 35/60 filler targets; this cut handles the remaining
walls/non-fillers. The headline number is the *type-conditional spatial address* — each
element addressed by the descriptor appropriate to its class — which is the real
"visual-topological address" the paper proposes.

Schemes (oracle r=1, real pools, GT-in-pool 100%, expected Top-k with analytic ties):
  coarse (storey+class) · +object_type · +spatial_address · +both. Reported overall and
  split by subgroup (filler / wall / other), so the per-class story is explicit.

Reuses `rerank_prize` (pool loading, tie math). No GPU, no Neo4j.
Caveat: oracle r=1 ceiling; realizable needs structured extractors for each descriptor
(position-slot + wall connection/opening counts) — all are photo/floorplan-recoverable,
which is the whole point of the spatial-address criterion.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
import rerank_prize as rp
from reconstruct_position_index import load_position_index
from wall_fingerprint import load_wall_fingerprint, wall_address

DEFAULT_POS = REPO_ROOT / "data" / "references" / "position_index.jsonl"
DEFAULT_WALL = REPO_ROOT / "data" / "references" / "wall_fingerprint.jsonl"


def spatial_address(guid: str, pos: dict, wallfp: dict):
    """Type-conditional address: filler slot, else wall fingerprint, else None."""
    if guid in pos:
        p = pos[guid]
        return ("pos", p["wall_position_index"], p["wall_child_total"])
    wa = wall_address(wallfp.get(guid))
    if wa is not None:
        return ("wall",) + wa
    return None


def subgroup(guid: str, pos: dict, wallfp: dict) -> str:
    if guid in pos:
        return "filler"
    if guid in wallfp:
        return "wall"
    return "other"


def feats(guid: str, tc: dict, idx: dict, pos: dict, wallfp: dict) -> dict:
    e = idx.get(guid, {})
    return {
        "storey": rp._storey_key(tc.get("ref_storey") or e.get("storey_name")),
        "ifc_class": tc.get("ref_type") or tc.get("type") or e.get("ifc_class"),
        "object_type": e.get("object_type"),
        "spatial_address": spatial_address(guid, pos, wallfp),
    }


def score(pool: dict, idx: dict, pos: dict, wallfp: dict, gt: str, weights: dict) -> dict:
    gf = feats(gt, pool[gt], idx, pos, wallfp)
    out = {}
    for guid, tc in pool.items():
        cf = feats(guid, tc, idx, pos, wallfp)
        out[guid] = sum(w * (cf.get(f) is not None and cf.get(f) == gf.get(f))
                        for f, w in weights.items())
    return out


SCHEMES = {
    "coarse_storey_class": {"storey": 1.0, "ifc_class": 1.0},
    "plus_object_type": {"storey": 1.0, "ifc_class": 1.0, "object_type": 1.0},
    "plus_spatial_address": {"storey": 1.0, "ifc_class": 1.0, "spatial_address": 1.0},
    "plus_both": {"storey": 1.0, "ifc_class": 1.0, "object_type": 1.0, "spatial_address": 1.0},
}


def run(idx: dict, cases: list, pos: dict, wallfp: dict) -> dict:
    rows = {k: [] for k in SCHEMES}
    groups = {k: [] for k in SCHEMES}  # subgroup per case (aligned with rows)
    sub_counts = {"filler": 0, "wall": 0, "other": 0}
    for case in cases:
        gt = case["scenario"]["ground_truth"]["target_guid"]
        pool = rp.pool_candidates(case)
        if gt not in pool:
            continue
        g = subgroup(gt, pos, wallfp)
        sub_counts[g] += 1
        for k, w in SCHEMES.items():
            rows[k].append(rp._rank_stats(score(pool, idx, pos, wallfp, gt, w), gt))
            groups[k].append(g)

    def agg(scheme, sub=None):
        rs = [r for r, gp in zip(rows[scheme], groups[scheme]) if sub is None or gp == sub]
        return rp.aggregate(rs) if rs else None

    return {
        "n_cases": len(rows["coarse_storey_class"]),
        "subgroup_counts": sub_counts,
        "metrics_overall": {k: agg(k) for k in SCHEMES},
        "metrics_by_subgroup": {
            sub: {k: agg(k, sub) for k in SCHEMES} for sub in ("filler", "wall", "other")
        },
    }


def wall_ceiling(idx: dict, cases: list, pos: dict, wallfp: dict) -> dict:
    """|C| ceiling within same-storey walls for the wall targets: coarse vs +object_type
    vs +wall fingerprint (the probe that motivated this cut)."""
    walls_by_storey: dict = {}
    for g, e in idx.items():
        if e["ifc_class"] in ("IfcWall", "IfcWallStandardCase"):
            walls_by_storey.setdefault(e.get("storey_name"), []).append(g)
    wall_targets = [c["scenario"]["ground_truth"]["target_guid"] for c in cases]
    wall_targets = [g for g in wall_targets
                    if g in idx and idx[g]["ifc_class"] in ("IfcWall", "IfcWallStandardCase")]
    coarse, obj, fp = [], [], []
    for g in wall_targets:
        sib = walls_by_storey.get(idx[g].get("storey_name"), [])
        coarse.append(len(sib))
        ot = idx[g].get("object_type")
        obj.append(sum(1 for s in sib if idx[s].get("object_type") == ot))
        wa = wall_address(wallfp.get(g))
        fp.append(sum(1 for s in sib if wall_address(wallfp.get(s)) == wa))
    med = lambda xs: statistics.median(xs) if xs else None
    return {
        "n_wall_targets": len(wall_targets),
        "coarse_median": med(coarse), "plus_object_type_median": med(obj),
        "plus_wall_fp_median": med(fp),
        "uniquely_id_by_wall_fp": sum(1 for c in fp if c == 1),
        "uniquely_id_by_object_type": sum(1 for c in obj if c == 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", type=Path, default=rp.DEFAULT_INDEX)
    ap.add_argument("--traces", type=Path, default=rp.DEFAULT_TRACES)
    ap.add_argument("--position", type=Path, default=DEFAULT_POS)
    ap.add_argument("--wall", type=Path, default=DEFAULT_WALL)
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "output" / "spatial_address_ceiling.json")
    args = ap.parse_args()

    idx = rp.load_index(args.index)
    cases = rp.load_cases(args.traces)
    pos = load_position_index(args.position)
    wallfp = load_wall_fingerprint(args.wall)

    res = run(idx, cases, pos, wallfp)
    res["wall_ceiling"] = wall_ceiling(idx, cases, pos, wallfp)

    sc = res["subgroup_counts"]
    print(f"\n=== Idea 3c — spatial-address ceiling ({res['n_cases']} targets: "
          f"{sc['filler']} fillers / {sc['wall']} walls / {sc['other']} other) ===")
    print(f"\nWall |C| ceiling (within same-storey walls, {res['wall_ceiling']['n_wall_targets']} wall targets):")
    wc = res["wall_ceiling"]
    print(f"  coarse {wc['coarse_median']} → +object_type {wc['plus_object_type_median']} "
          f"→ +wall fingerprint {wc['plus_wall_fp_median']}  "
          f"(uniquely id: wall-fp {wc['uniquely_id_by_wall_fp']} vs object_type {wc['uniquely_id_by_object_type']})")

    print(f"\nOracle Top-k on real pools (type-conditional spatial address):")
    print(f"  {'scheme':<24}{'Top-1':<8}{'Top-5':<8}{'Top-10':<8}{'MRR'}")
    print("  " + "-" * 50)
    for k in SCHEMES:
        d = res["metrics_overall"][k]
        print(f"  {k:<24}{d['top1']:<8}{d['top5']:<8}{d['top10']:<8}{d['mrr']}")
    for sub in ("filler", "wall"):
        print(f"\n  [{sub} subgroup, n={sc[sub]}]")
        for k in ("coarse_storey_class", "plus_object_type", "plus_spatial_address", "plus_both"):
            d = res["metrics_by_subgroup"][sub][k]
            if d:
                print(f"    {k:<24}Top-1 {d['top1']:<7}Top-10 {d['top10']}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(res, indent=2) + "\n")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
