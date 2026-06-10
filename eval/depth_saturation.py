#!/usr/bin/env python3
"""
Depth-saturation analysis — how DEEP should the relational fingerprint be? (Neo4j-free)

The earlier cuts varied the FEATURE SET; this varies the relational DEPTH directly on the
enriched IFC graph, to settle "depth was never where the discrimination lived" with a
measured curve rather than the thesis's per-hop anecdote.

For each held-out target we compute its confusable-set size |C_k| as a function of
relational depth k = 0..3, using a Weisfeiler–Lehman (WL) typed-neighbourhood signature —
the standard way to summarise a k-hop neighbourhood into one canonical node label, i.e. the
oracle "depth-k structural fingerprint". Two curves:

  - ORACLE |C_k| (r=1): pure information. WL refines labels each hop, so this keeps
    shrinking (often to 1) — that is *expected*; it is the information ceiling.
  - REALIZABLE |C_k|: discount each added hop by its photo-extraction reliability r_hop
    (thesis results.md:252 — hop-1 predicate ~0.40, hop-2 ~0.05, hop-3 ~0). A depth-k
    relation only pays when ALL k hops are read correctly, joint p_k = ∏_{h≤k} r_hop:
        E_k = p_k · oracle_k + (1 - p_k) · E_{k-1}      (E_0 = oracle_0 = attribute pool)
    This isolates the *realizable* marginal value of each extra hop beyond attributes.

The depth where REALIZABLE marginal reduction → 0 is the empirically-justified max depth.

Graph: nodes = `element_index.jsonl` elements (deduped, 852); edges reconstructed offline
from the IFC (same geometry as `ifc_engine`): FILLS (window/door↔host wall), NEXT_TO
(consecutive co-fillers), CONNECTS_TO (wall↔wall), ADJACENT_TO (cross-type <1500mm same
storey); CONTINUOUS folded into the node label. No GPU, no Neo4j.

Caveats: (1) WL oracle over-discriminates (exact neighbour labels a photo can't read) — that
is exactly why the realizable discount matters. (2) r_hop are thesis per-hop predicate
proxies; the *shape* (collapse after hop-1) is the robust result. (3) universe = element_index
(852) not the live graph; report relative depth saturation, not absolute |C|.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = REPO_ROOT / "data" / "references" / "element_index.jsonl"
DEFAULT_CASES = REPO_ROOT / "data" / "test_sets" / "cases_ap_heldout_e2e.jsonl"
DEFAULT_IFC = REPO_ROOT / "data" / "ifc_models" / "AdvancedProject.ifc"

# Per-hop photo-extraction reliability (thesis results.md:252 — Hop1 pred ~0.40, Hop2 0.05,
# Hop3 ~0). r_hop[k] = reliability of correctly reading the k-th hop of a relation chain.
R_HOP = {1: 0.40, 2: 0.05, 3: 0.005}


def _storey_key(v):
    if v in (None, ""):
        return None
    import re
    m = re.match(r"\s*(\d+)", str(v))
    return m.group(1) if m else str(v).strip()


def load_universe(path: Path) -> dict[str, dict]:
    by: dict[str, dict] = {}
    for l in path.read_text().splitlines():
        if l.strip():
            r = json.loads(l)
            by[r["global_id"]] = r
    return by


def build_edges(universe: dict[str, dict], ifc_path: Path) -> dict[str, list[tuple[str, str]]]:
    """Reconstruct the enriched typed graph offline. Returns guid -> [(edge_type, neighbour_guid)]."""
    import ifcopenshell
    import ifcopenshell.util.element as eu
    import ifcopenshell.util.placement
    import numpy as np

    ifc = ifcopenshell.open(str(ifc_path))
    nbrs: dict[str, list[tuple[str, str]]] = defaultdict(list)
    present = set(universe)

    def add(a, b, t):
        if a in present and b in present and a != b:
            nbrs[a].append((t, b))
            nbrs[b].append((t, a))

    # FILLS: window/door -> host wall (voids+fills chain)
    op2wall = {}
    for v in ifc.by_type("IfcRelVoidsElement"):
        o, w = v.RelatedOpeningElement, v.RelatingBuildingElement
        if o and w:
            op2wall[o.GlobalId] = w.GlobalId
    wall_fillers: dict[str, list] = defaultdict(list)
    for f in ifc.by_type("IfcRelFillsElement"):
        o, el = f.RelatingOpeningElement, f.RelatedBuildingElement
        if o and el and o.GlobalId in op2wall:
            add(el.GlobalId, op2wall[o.GlobalId], "FILLS")
            wall_fillers[op2wall[o.GlobalId]].append(el)

    # NEXT_TO: consecutive co-fillers on the same wall+storey (project on wall axis)
    def storey_name(el):
        c = eu.get_container(el)
        while c and not c.is_a("IfcBuildingStorey"):
            c = eu.get_container(c)
        return c.Name if c else "_"
    for wall_guid, fillers in wall_fillers.items():
        if len(fillers) < 2:
            continue
        try:
            wall = ifc.by_guid(wall_guid)
            wm = ifcopenshell.util.placement.get_local_placement(wall.ObjectPlacement)
            wdir = np.array([wm[0][0], wm[1][0], wm[2][0]])
            worg = np.array([wm[0][3], wm[1][3], wm[2][3]])
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
                    proj.append((float(np.dot(np.array([m[0][3], m[1][3], m[2][3]]) - worg, wdir)), el))
                except Exception:
                    pass
            proj.sort(key=lambda x: x[0])
            for i in range(len(proj) - 1):
                add(proj[i][1].GlobalId, proj[i + 1][1].GlobalId, "NEXT_TO")

    # CONNECTS_TO: wall<->wall path connections
    for rel in ifc.by_type("IfcRelConnectsPathElements"):
        a, b = rel.RelatingElement, rel.RelatedElement
        if a and b:
            add(a.GlobalId, b.GlobalId, "CONNECTS_TO")

    # ADJACENT_TO: cross-type, same storey, centroid in (100,1500]mm
    by_st: dict[str, list[dict]] = defaultdict(list)
    for e in universe.values():
        if e.get("centroid"):
            by_st[e.get("storey_name") or ""].append(e)
    for grp in by_st.values():
        for i in range(len(grp)):
            a = grp[i]; ca = a["centroid"]
            for j in range(i + 1, len(grp)):
                b = grp[j]
                if a["ifc_class"] == b["ifc_class"]:
                    continue
                cb = b["centroid"]
                d = ((ca["x"] - cb["x"]) ** 2 + (ca["y"] - cb["y"]) ** 2 + (ca["z"] - cb["z"]) ** 2) ** 0.5
                if 100.0 < d <= 1500.0:
                    add(a["global_id"], b["global_id"], "ADJACENT_TO")
    return nbrs


def node_label0(e: dict) -> tuple:
    c = (e.get("psets") or {}).get("Constraints", {}) or {}
    base = str(c.get("Base Constraint", "")).strip()
    top = str(c.get("Top Constraint", "")).strip()
    continuous = bool(base and top and "Unconnected" not in top and base != top)
    return (_storey_key(e.get("storey_name")), e.get("ifc_class"), e.get("object_type"), continuous)


def wl_signatures(universe: dict, nbrs: dict, K: int) -> list[dict[str, int]]:
    """WL relabelling. Returns [labels_0, .., labels_K], each guid -> compact int color."""
    guids = list(universe)
    raw = {g: node_label0(universe[g]) for g in guids}
    levels = []
    # compress to ints
    def compress(rawmap):
        idx = {}
        out = {}
        for g, lab in rawmap.items():
            out[g] = idx.setdefault(lab, len(idx))
        return out
    cur = compress(raw)
    levels.append(cur)
    for _ in range(K):
        nxt_raw = {}
        for g in guids:
            multiset = tuple(sorted((t, cur[u]) for (t, u) in nbrs.get(g, [])))
            nxt_raw[g] = (cur[g], multiset)
        cur = compress(nxt_raw)
        levels.append(cur)
    return levels


def confusable_sizes(levels: list[dict[str, int]], targets: list[str]) -> list[list[int]]:
    """For each depth k, |C_k(t)| = #nodes sharing t's color at level k, for each target."""
    out = []
    for lab in levels:
        from collections import Counter
        counts = Counter(lab.values())
        out.append([counts[lab[t]] for t in targets])
    return out


def analyze(universe: dict, nbrs: dict, targets: list[str], K: int = 3) -> dict:
    levels = wl_signatures(universe, nbrs, K)
    csz = confusable_sizes(levels, targets)  # csz[k] = list of |C_k| over targets
    oracle = [statistics.median(c) for c in csz]

    # realizable: E_k = p_k*oracle_k + (1-p_k)*E_{k-1}, p_k = prod r_hop up to k (per target, then median)
    realizable_per_target = []
    for ti in range(len(targets)):
        E = float(csz[0][ti])
        prow = [E]
        p = 1.0
        for k in range(1, K + 1):
            p *= R_HOP.get(k, 0.0)
            E = p * csz[k][ti] + (1 - p) * E
            prow.append(E)
        realizable_per_target.append(prow)
    realizable = [statistics.median(realizable_per_target[ti][k] for ti in range(len(targets)))
                  for k in range(K + 1)]

    edge_counts = {}
    for g in nbrs:
        for (t, _) in nbrs[g]:
            edge_counts[t] = edge_counts.get(t, 0) + 1
    edge_counts = {t: n // 2 for t, n in edge_counts.items()}  # undirected

    return {
        "n_targets": len(targets),
        "universe": len(universe),
        "edge_counts": edge_counts,
        "r_hop": R_HOP,
        "oracle_median_pool_by_depth": {k: oracle[k] for k in range(K + 1)},
        "realizable_median_pool_by_depth": {k: round(realizable[k], 1) for k in range(K + 1)},
        "oracle_marginal_reduction": {k: round(oracle[k - 1] - oracle[k], 1) for k in range(1, K + 1)},
        "realizable_marginal_reduction": {k: round(realizable[k - 1] - realizable[k], 2) for k in range(1, K + 1)},
    }


def make_figure(res: dict, out_path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    K = max(res["oracle_median_pool_by_depth"])
    xs = list(range(K + 1))
    orc = [res["oracle_median_pool_by_depth"][k] for k in xs]
    rea = [res["realizable_median_pool_by_depth"][k] for k in xs]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.plot(xs, orc, "o-", color="tab:green", label="oracle |C_k| (r=1, information ceiling)")
    ax.plot(xs, rea, "s--", color="tab:red", label="realizable |C_k| (per-hop reliability)")
    for x, (a, b) in enumerate(zip(orc, rea)):
        ax.annotate(f"{a:g}", (x, a), textcoords="offset points", xytext=(0, 6), fontsize=8, ha="center", color="tab:green")
        ax.annotate(f"{b:g}", (x, b), textcoords="offset points", xytext=(0, -12), fontsize=8, ha="center", color="tab:red")
    ax.set_xticks(xs)
    ax.set_xlabel("relational depth k (hops)")
    ax.set_ylabel("median confusable-set |C_k|")
    ax.set_title("Depth saturation — does deeper relation help? (oracle vs realizable)")
    ax.set_yscale("log")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    print(f"wrote {out_path}")


def load_targets(universe: dict, cases: Path) -> list[str]:
    gts = [(json.loads(l).get("ground_truth") or {}).get("target_guid")
           for l in cases.read_text().splitlines() if l.strip()]
    return [g for g in gts if g in universe]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    ap.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    ap.add_argument("--ifc", type=Path, default=DEFAULT_IFC)
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "output" / "depth_saturation.json")
    ap.add_argument("--fig", type=Path)
    args = ap.parse_args()

    universe = load_universe(args.index)
    nbrs = build_edges(universe, args.ifc)
    targets = load_targets(universe, args.cases)
    res = analyze(universe, nbrs, targets, K=args.depth)

    print(f"\n=== Depth saturation ({res['n_targets']} targets / {res['universe']} elements) ===")
    print(f"edges: {res['edge_counts']}   r_hop: {res['r_hop']}")
    print(f"\n  {'depth k':<9}{'oracle |C_k|':<15}{'realizable |C_k|':<18}{'oracle Δ':<11}{'realizable Δ'}")
    print("  " + "-" * 62)
    for k in range(args.depth + 1):
        od = res["oracle_marginal_reduction"].get(k, "")
        rd = res["realizable_marginal_reduction"].get(k, "")
        print(f"  {k:<9}{res['oracle_median_pool_by_depth'][k]:<15}"
              f"{res['realizable_median_pool_by_depth'][k]:<18}{str(od):<11}{rd}")
    # verdict
    rmr = res["realizable_marginal_reduction"]
    sat = next((k for k in sorted(rmr) if abs(rmr[k]) < 1.0), None)
    print(f"\n  realizable marginal reduction < 1 element first at depth {sat} "
          f"→ relational depth saturates at k={ (sat-1) if sat else args.depth }")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(res, indent=2) + "\n")
    print(f"wrote {args.out}")
    if args.fig:
        make_figure(res, args.fig)


if __name__ == "__main__":
    main()
