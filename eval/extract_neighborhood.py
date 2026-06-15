"""Cache a REAL multi-hop neighbourhood from the IFC graph for the depth figure (Figure 2).

BFS depth-3 from a real held-out filler target over the reconstructed IFC edges
(depth_saturation.build_edges); save nodes (guid, hop, ifc type) and the real edges among them
(predicate). Lets fig_depth_sample.py draw a real neighbourhood without re-parsing the 44 MB IFC.

Run:  .venv/bin/python eval/extract_neighborhood.py
Out:  output/depth_neighborhood.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "eval"))
from depth_saturation import load_universe, build_edges, DEFAULT_INDEX, DEFAULT_IFC

OUT = REPO / "output"
TARGET = "1ebX2H7F12su$wtPbeYATe"  # AP_SK_234 filler; shells {1:2, 2:4, 3:13}
DEPTH = 3
MAX_PER_HOP = 8  # cap hop-3 fan-out so the figure stays legible


def short_type(t: str | None) -> str:
    if not t:
        return "?"
    return t.replace("IfcWallStandardCase", "Wall").replace("Ifc", "")


def main():
    uni = load_universe(DEFAULT_INDEX)
    nbrs = build_edges(uni, DEFAULT_IFC)

    hop = {TARGET: 0}
    frontier = [TARGET]
    for d in range(1, DEPTH + 1):
        nxt = []
        for u in frontier:
            for (_, v) in nbrs.get(u, []):
                if v not in hop:
                    hop[v] = d
                    nxt.append(v)
        # cap fan-out per hop for legibility (keep first MAX_PER_HOP)
        if len(nxt) > MAX_PER_HOP:
            for v in nxt[MAX_PER_HOP:]:
                del hop[v]
            nxt = nxt[:MAX_PER_HOP]
        frontier = nxt

    nodes = [{"guid": g, "hop": h, "type": short_type((uni.get(g) or {}).get("ifc_class"))}
             for g, h in hop.items()]
    edges = []
    seen_pairs = set()
    for u in hop:
        for (t, v) in nbrs.get(u, []):
            if v in hop and (v, u) not in seen_pairs:
                seen_pairs.add((u, v))
                edges.append({"u": u, "v": v, "rel": t})

    out = {"target": TARGET, "case": "AP_SK_234", "depth": DEPTH, "nodes": nodes, "edges": edges,
           "hop_counts": {str(d): sum(1 for n in nodes if n["hop"] == d) for d in range(DEPTH + 1)}}
    OUT.mkdir(exist_ok=True)
    json.dump(out, open(OUT / "depth_neighborhood.json", "w"), indent=2)
    print("nodes", len(nodes), "edges", len(edges), "hop_counts", out["hop_counts"])


if __name__ == "__main__":
    main()
