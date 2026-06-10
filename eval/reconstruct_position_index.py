#!/usr/bin/env python3
"""
Offline reconstruction of the NEXT_TO position-slot feature (Neo4j-free).

`ifc_engine._create_next_to_edges` computes `wall_position_index` / `wall_child_total`
(the `position_context` feature — "Nth filler from one end of the host wall, of M") and
writes them ONLY into Neo4j. `element_index.jsonl` does NOT carry them, so the Idea-3a
fingerprint/rerank cuts (which read the flat index) omitted this feature entirely. This
script replicates the engine's projection logic on the raw IFC so the cuts can include it
without standing up Neo4j.

Algorithm (mirrors ifc_engine._create_next_to_edges):
  1. FILLS chain: window/door -[FillsElement]-> opening -[VoidsElement]-> host wall.
  2. Group fillers by (host wall, containing storey) — stacked windows on multi-storey
     walls are NOT neighbours.
  3. Project each filler centroid onto the wall's local X-axis; sort; assign 0-based index.
Output: JSONL of {guid, wall_guid, wall_position_index, wall_child_total} for every filler
on a multi-filler wall+storey group.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IFC = REPO_ROOT / "data" / "ifc_models" / "AdvancedProject.ifc"
DEFAULT_OUT = REPO_ROOT / "data" / "references" / "position_index.jsonl"


def reconstruct(ifc_path: Path) -> list[dict]:
    import ifcopenshell
    import ifcopenshell.util.element as eu
    import ifcopenshell.util.placement
    import numpy as np

    ifc = ifcopenshell.open(str(ifc_path))

    op2wall = {}
    for v in ifc.by_type("IfcRelVoidsElement"):
        o, w = v.RelatedOpeningElement, v.RelatingBuildingElement
        if o and w:
            op2wall[o.GlobalId] = w.GlobalId
    wall_fillers: dict[str, list] = defaultdict(list)
    for f in ifc.by_type("IfcRelFillsElement"):
        o, el = f.RelatingOpeningElement, f.RelatedBuildingElement
        if o and el and o.GlobalId in op2wall:
            wall_fillers[op2wall[o.GlobalId]].append(el)

    def storey_name(el) -> str:
        c = eu.get_container(el)
        while c and not c.is_a("IfcBuildingStorey"):
            c = eu.get_container(c)
        return c.Name if c else "_unknown"

    rows: list[dict] = []
    for wall_guid, fillers in wall_fillers.items():
        if len(fillers) < 2:
            continue
        try:
            wall = ifc.by_guid(wall_guid)
            wm = ifcopenshell.util.placement.get_local_placement(wall.ObjectPlacement)
            wdir = np.array([wm[0][0], wm[1][0], wm[2][0]])
            worigin = np.array([wm[0][3], wm[1][3], wm[2][3]])
        except Exception:
            continue
        groups: dict[str, list] = defaultdict(list)
        for el in fillers:
            groups[storey_name(el)].append(el)
        for grp in groups.values():
            proj = []
            for el in grp:
                try:
                    m = ifcopenshell.util.placement.get_local_placement(el.ObjectPlacement)
                    c = np.array([m[0][3], m[1][3], m[2][3]])
                    proj.append((float(np.dot(c - worigin, wdir)), el))
                except Exception:
                    continue
            if len(proj) < 2:
                continue
            proj.sort(key=lambda x: x[0])
            total = len(proj)
            for idx, (_, el) in enumerate(proj):
                rows.append({
                    "guid": el.GlobalId,
                    "wall_guid": wall_guid,
                    "wall_position_index": idx,
                    "wall_child_total": total,
                })
    return rows


def load_position_index(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {r["guid"]: r for r in (json.loads(l) for l in path.read_text().splitlines() if l.strip())}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ifc", type=Path, default=DEFAULT_IFC)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    rows = reconstruct(args.ifc)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    totals = sorted({r["wall_child_total"] for r in rows})
    print(f"reconstructed position-slot for {len(rows)} fillers on multi-filler walls")
    print(f"  distinct wall_child_total values: {totals}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
