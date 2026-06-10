#!/usr/bin/env python3
"""
Offline wall / non-filler spatial fingerprint (Idea 3c, first cut; Neo4j-free).

`position_context` (the NEXT_TO slot) is the spatial address for window/door *fillers*
(35/60 held-out targets). Walls are *hosts*, not fillers — they have no position-slot, so
the 25/60 non-filler targets need a different descriptor. This reconstructs a wall
fingerprint from the raw IFC + `element_index`, using descriptors that are both
IFC-computable and recoverable from a site photo / floorplan:

  - connection_degree   : # CONNECTS_TO neighbours (junctions the wall participates in)
  - junction_sig        : multiset of connection types (ATSTART/ATEND/ATPATH) — corner vs T
  - hosted_opening_count : # windows/doors the wall hosts (FILLS reverse) — countable in a photo
  - length_band         : <2m / 2-5m / 5-10m / >10m (from IFC Length)
  - is_external         : exterior vs interior wall

Probe result (22 wall targets, within same-storey walls): coarse median |C| 110 →
+object_type 26 → +this fingerprint **2** (10/22 uniquely identified, vs 0/22 by object_type).

Output: JSONL guid -> {connection_degree, junction_sig, hosted_opening_count, length_band,
is_external} for every wall in the model.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IFC = REPO_ROOT / "data" / "ifc_models" / "AdvancedProject.ifc"
DEFAULT_INDEX = REPO_ROOT / "data" / "references" / "element_index.jsonl"
DEFAULT_OUT = REPO_ROOT / "data" / "references" / "wall_fingerprint.jsonl"

WALL_CLASSES = ("IfcWall", "IfcWallStandardCase")


def length_band(L) -> str | None:
    if not L:
        return None
    return "<2m" if L < 2000 else "2-5m" if L < 5000 else "5-10m" if L < 10000 else ">10m"


def reconstruct(ifc_path: Path, index_path: Path) -> list[dict]:
    import ifcopenshell

    ifc = ifcopenshell.open(str(ifc_path))
    idx = {}
    for l in index_path.read_text().splitlines():
        if l.strip():
            r = json.loads(l)
            idx[r["global_id"]] = r

    # CONNECTS_TO degree + junction signature
    deg: Counter = Counter()
    jtype: dict[str, Counter] = defaultdict(Counter)
    for rel in ifc.by_type("IfcRelConnectsPathElements"):
        a, b = rel.RelatingElement, rel.RelatedElement
        if not a or not b:
            continue
        deg[a.GlobalId] += 1
        deg[b.GlobalId] += 1
        jtype[a.GlobalId][str(getattr(rel, "RelatingConnectionType", None))] += 1
        jtype[b.GlobalId][str(getattr(rel, "RelatedConnectionType", None))] += 1

    # hosted opening count (FILLS reverse: wall <- opening <- filler)
    op2wall = {}
    for v in ifc.by_type("IfcRelVoidsElement"):
        o, w = v.RelatedOpeningElement, v.RelatingBuildingElement
        if o and w:
            op2wall[o.GlobalId] = w.GlobalId
    host_open: Counter = Counter()
    for f in ifc.by_type("IfcRelFillsElement"):
        o = f.RelatingOpeningElement
        if o and o.GlobalId in op2wall:
            host_open[op2wall[o.GlobalId]] += 1

    rows = []
    for guid, e in idx.items():
        if e["ifc_class"] not in WALL_CLASSES:
            continue
        L = (e.get("dimensions") or {}).get("Length")
        sig = ",".join(f"{k}:{n}" for k, n in sorted(jtype.get(guid, {}).items()))
        rows.append({
            "guid": guid,
            "connection_degree": deg.get(guid, 0),
            "junction_sig": sig,
            "hosted_opening_count": host_open.get(guid, 0),
            "length_band": length_band(L),
            "is_external": e.get("is_external"),
        })
    return rows


def load_wall_fingerprint(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {r["guid"]: r for r in (json.loads(l) for l in path.read_text().splitlines() if l.strip())}


# the discriminative descriptor tuple used as the wall "spatial address"
def wall_address(fp: dict | None) -> tuple | None:
    if not fp:
        return None
    return (fp["connection_degree"], fp["hosted_opening_count"], fp["length_band"], fp["is_external"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ifc", type=Path, default=DEFAULT_IFC)
    ap.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    rows = reconstruct(args.ifc, args.index)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    from collections import Counter as C
    print(f"reconstructed wall fingerprint for {len(rows)} walls")
    print(f"  connection_degree dist: {dict(sorted(C(r['connection_degree'] for r in rows).items()))}")
    print(f"  hosted_opening_count >0: {sum(1 for r in rows if r['hosted_opening_count'])}/{len(rows)}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
