"""Live retrieval reproduction — the `--live` engine for run_benchmark.py.

Runs the REAL symbolic pipeline (plan -> retrieve -> rank) against a live Neo4j graph,
using the frozen G8 extraction as `precomputed_constraints` (no GPU / VLM needed). This is
the documented Phase-0 live-closeout path (config.yaml lines 40-41): it proves the in-repo
graph build (scripts/graph_build 01->02) + QueryPlanner + RetrievalBackend faithfully
reconstruct the frozen pipeline's retrieval, which is the gate for retiring `mscd_demo`.

What reproduces exactly: GT-in-pool, Top-1, Top-5, and pool sizes. Top-10/MRR differ by 2 cases
(Top-10 26.7 vs frozen 30.0) because of deterministic tie-break ordering among IDENTICAL siblings
in the pool tail: the fresh in-repo graph inserts nodes in a different order than the original
mscd_demo graph, so same-storey+type siblings (indistinguishable without the spatial address) sort
differently past rank 5. The frozen G8 used NO rerank (rerank_gain=None on all 60 cases; shortlist
== raw retrieval order), so this is not a rerank gap. The live pipeline is itself fully deterministic
(two runs are byte-identical, 60/60) — the repeatability the design claims.

Usage (via run_benchmark):  python eval/run_benchmark.py --live
Returns rows in the same shape score_case() consumes from frozen traces.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

CASES = REPO_ROOT / "data" / "test_sets" / "cases_ap_heldout_e2e.jsonl"
FROZEN = REPO_ROOT / "eval" / "fixtures" / "traces" / "g8_posctx_dim.jsonl"
IFC = REPO_ROOT / "data" / "ifc_models" / "AdvancedProject.ifc"


def _load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def _precomputed_constraints(frozen_rows: list[dict]) -> dict[str, Any]:
    """{case_id: Constraints} from the frozen G8 extraction (internals.constraints)."""
    from aec_interpreter.neurosym.types import Constraints

    out: dict[str, Any] = {}
    for r in frozen_rows:
        cid = r.get("scenario_id")
        con = (r.get("internals") or {}).get("constraints")
        if cid and con:
            out[cid] = Constraints.model_validate(con)
    return out


def _row_from_traces(eval_trace: Any, pipeline_trace: Any) -> dict:
    """Merge EvalTrace + PipelineTrace into the dict shape score_case() reads.

    score_case needs: scenario.ground_truth.target_guid, interpreter_output.candidates,
    internals.retrieval_results[*].candidates[*].guid, final_pool_size, initial_pool_size.
    The full retrieved pool (GT-in-pool) lives in PipelineTrace.retrieval_results, NOT EvalTrace.
    """
    row = eval_trace.model_dump(mode="json")
    retrieval_results = []
    for res in (pipeline_trace.retrieval_results or []):
        cands = getattr(res, "candidates", None) or []
        retrieval_results.append(
            {"candidates": [{"guid": c.get("guid")} for c in cands if isinstance(c, dict) and c.get("guid")]}
        )
    row.setdefault("internals", {})["retrieval_results"] = retrieval_results
    return row


async def _run_all(p0_strategy: str) -> list[dict]:
    from py2neo import Graph
    from aec_interpreter.ifc_engine import IFCEngine
    from aec_interpreter.neurosym.retrieval_backend import RetrievalBackend
    from aec_interpreter.neurosym.pipeline import run_pipeline_case

    graph = Graph("bolt://localhost:7687", auth=("neo4j", "password"))
    print(f"[live] Neo4j connected — {graph.run('MATCH (e:IFCElement) RETURN count(e)').evaluate()} elements")
    print("[live] parsing IFC (populates engine.spatial_index for pool sizing)…", flush=True)
    engine = IFCEngine(str(IFC), neo4j_conn=graph)

    backend = RetrievalBackend(
        engine=engine,
        retrieval_mode="neo4j",
        visual_aligner=None,
        use_clip=False,
        p0_strategy=p0_strategy,        # paper-canonical = p0_union_p1
        size_cluster_mode="soft",       # matches config.yaml
        size_band_mode="hard",
    )

    cases = _load_jsonl(CASES)
    precomp = _precomputed_constraints(_load_jsonl(FROZEN))
    print(f"[live] {len(cases)} cases, {len(precomp)} precomputed constraints, p0_strategy={p0_strategy}")

    rows: list[dict] = []
    for i, case in enumerate(cases, 1):
        eval_trace, pipeline_trace = await run_pipeline_case(
            case=case,
            condition_overrides={"use_images": False},
            constraints_model="lora",          # + precomputed => no VLM/LLM call
            retrieval_backend=backend,
            llm=None,
            run_id="live",
            image_dir="",
            engine=engine,
            image_parser=None,
            lora_extractor=None,
            precomputed_constraints=precomp,
        )
        rows.append(_row_from_traces(eval_trace, pipeline_trace))
        if i % 10 == 0:
            print(f"[live]   {i}/{len(cases)} cases", flush=True)
    return rows


def run_live(p0_strategy: str = "p0_union_p1") -> list[dict]:
    """Public entry: returns scored-ready rows from a live Neo4j run."""
    return asyncio.run(_run_all(p0_strategy))


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--p0", default="p0_union_p1", help="p0 strategy (p0_union_p1 | p0_intersect_p1 | ...)")
    ap.add_argument("--out", type=Path, help="write raw rows JSONL")
    a = ap.parse_args()
    rows = run_live(a.p0)
    if a.out:
        a.out.write_text("\n".join(json.dumps(r) for r in rows))
        print(f"wrote {len(rows)} rows -> {a.out}")
    # quick GT-in-pool sanity
    from collections import Counter
    gip = sum(1 for r in rows if (r.get("scenario") or {}).get("ground_truth", {}).get("target_guid")
              in {c["guid"] for res in r["internals"]["retrieval_results"] for c in res["candidates"]})
    print(f"GT-in-pool: {gip}/{len(rows)}")
