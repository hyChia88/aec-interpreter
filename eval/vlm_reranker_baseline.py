"""#5 — Zero-shot VLM reranker baseline (the fair off-the-shelf end-to-end control).

The dense/lexical baselines (`external_baseline.py`) only test TEXT retrieval. The reviewer's
question is sharper: can a *strong general VLM*, given the marked-element images, recover the
relational slot and rank the pool — i.e. do the end-to-end matching the structured address does?
This harness answers it with the SAME base model the G8 LoRA was trained on, NO adapter, so any
gap to G8/oracle is attributable to the structured spatial address, not a weaker backbone.

Mechanism (per case):
  - pool guids + GT come from the frozen G8 traces (GT-in-pool 100%, identical to external_baseline).
  - candidate text = `external_baseline.cand_text` (class + storey + type + name — siblings tie).
  - images (site photo + marked floorplan) + note come from the live held-out case file.
  - Modal `BaseVLMReranker.rerank` returns a best->worst candidate ranking; unranked candidates
    are appended in pool order (recall-safe — GT is never dropped). Rank of GT -> Top-1/10 + MRR.

Reports the all-60 set and the filler-35 subset (the realized 67.6% comparison set), each with
bootstrap 95% CIs, and prints a ledger row to slot into the external_baseline figure/table.

Run (real, needs Modal authed + app deployed):
    .venv/bin/python eval/vlm_reranker_baseline.py
Validate the harness locally with no GPU (lexical stand-in for the VLM):
    .venv/bin/python eval/vlm_reranker_baseline.py --stub --limit 5
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parent
REPO = EVAL.parent
sys.path.insert(0, str(EVAL))
sys.path.insert(0, str(REPO))

from external_baseline import cand_text, lexical_scores
from rerank_prize import (load_index, load_cases, pool_candidates, _storey_key,
                          DEFAULT_INDEX, DEFAULT_TRACES)
from reconstruct_position_index import load_position_index
from spatial_address_ceiling import DEFAULT_POS

OUT = REPO / "output"
MODAL_APP = "mscd-vlm-lora3-inference"
MODAL_RERANKER = "BaseVLMReranker"
# Image set (gitignored) — mirrors eval/live_infer.py DEFAULT_DATA_ROOT.
DEFAULT_DATA_ROOT = Path("/home/hychi/projects/cmu/master_thesis/data_curation")


# ── case inputs (images + note), keyed by case_id == trace scenario_id ────────
def load_live_inputs() -> dict[str, dict]:
    from live_runner import CASES, _load_jsonl
    return {c["case_id"]: c for c in _load_jsonl(CASES)}


def case_images(case: dict, data_root: Path) -> list[Path]:
    inp = case.get("inputs", {})
    rels = list(inp.get("images") or [])
    if inp.get("floorplan_patch"):
        rels.append(inp["floorplan_patch"])
    return [data_root / r for r in rels]


def case_note(case: dict) -> str:
    inp = case.get("inputs", {})
    msgs = inp.get("chat_history") or []
    joined = "\n".join((m.get("text") or "").strip() for m in msgs if m.get("text"))
    return joined or (case.get("query_text") or "")


def case_metadata(case: dict) -> str:
    ctx = (case.get("inputs", {}).get("project_context") or {})
    bits = [f"[IFC Model] {ctx.get('model_code', 'AP')}"]
    for k in ("phase", "task_status", "location"):
        if ctx.get(k):
            bits.append(f"{k}: {ctx[k]}")
    return " ".join(bits)


# ── candidate set construction (scope + anti-positional shuffle) ──────────────
def _norm_class(s) -> str:
    return str(s or "").lower().replace("ifc", "").replace("standardcase", "").strip()


def _ckey(guid: str, idx: dict) -> tuple:
    e = idx.get(guid, {})
    return (_storey_key(e.get("storey_name")), _norm_class(e.get("ifc_class")))


def build_candidates(case_id: str, gt: str, pool: list[str], idx: dict,
                     scope: str, base_seed: int) -> list[str]:
    """Candidate guid list for a case, SHUFFLED so order-copying scores at chance.

    scope='full'     : the whole retrieved pool (apples-to-apples with the Top-1 ladder).
    scope='siblings' : GT + its same-(storey,class) confusables in the pool (the fine
                       visual-slot discrimination — the paper's contribution). GT-in-set
                       by construction, so chance = 1/|set|.
    """
    if scope == "siblings":
        k = _ckey(gt, idx)
        cands = [g for g in pool if _ckey(g, idx) == k]
        if gt not in cands:
            cands.append(gt)
    else:
        cands = list(pool)
    rng = random.Random(f"{base_seed}:{case_id}")     # per-case, reproducible
    rng.shuffle(cands)
    return cands


# ── rankers: VLM (Modal) and lexical stub ─────────────────────────────────────
def vlm_ranker(predictor, data_root: Path):
    """fn(case_id, cand_guids, idx) -> {ranking (best->worst guids), …} via Modal VLM.

    `cand_guids` is the already-scoped, already-shuffled candidate list; the model sees
    cand_text in that order and returns indices into it, which we map back to guids.
    """
    live = load_live_inputs()

    def rank(case_id: str, cand_guids: list[str], idx: dict) -> dict:
        lc = live.get(case_id)
        cands = [cand_text(g, idx) for g in cand_guids]
        if lc is None:
            return {"ranking": list(cand_guids), "valid_json": False, "note": "no_live_inputs"}
        img_paths = [p for p in case_images(lc, data_root) if p.exists()]
        out = predictor.rerank.remote(
            image_bytes_list=[p.read_bytes() for p in img_paths],
            candidates=cands,
            note_text=case_note(lc),
            metadata_text=case_metadata(lc),
        )
        order = out.get("ranking") or []
        ranked = [cand_guids[i] for i in order]
        ranked += [g for g in cand_guids if g not in set(ranked)]   # recall-safe tail
        return {"ranking": ranked, "valid_json": out.get("valid_json", False),
                "n_imgs": len(img_paths), "raw_output": out.get("raw_output", "")}

    return rank


def stub_ranker(case_dict: dict):
    """No-GPU stand-in: rank by lexical query<->candidate overlap. Validates the harness only."""
    def rank(case_id: str, cand_guids: list[str], idx: dict) -> dict:
        q = (case_dict[case_id]["scenario"].get("query_text") or "")
        pool = {g: {} for g in cand_guids}
        scores = lexical_scores(q, pool, idx)
        ranked = sorted(cand_guids, key=lambda g: (-scores.get(g, 0.0), g))
        return {"ranking": ranked, "valid_json": True, "stub": True}
    return rank


# ── metrics ───────────────────────────────────────────────────────────────────
def gt_rank(ranking: list[str], gt: str) -> int | None:
    return ranking.index(gt) + 1 if gt in ranking else None


def summarise(ranks: list[int | None]) -> dict:
    n = len(ranks)
    if n == 0:
        return {"n": 0, "top1": 0.0, "top10": 0.0, "mrr": 0.0, "top1_ci95": [0.0, 0.0]}
    hits1 = [1.0 if r == 1 else 0.0 for r in ranks]
    hits10 = [1.0 if (r is not None and r <= 10) else 0.0 for r in ranks]
    rr = [1.0 / r if r else 0.0 for r in ranks]
    return {
        "n": n,
        "top1": 100 * sum(hits1) / n,
        "top10": 100 * sum(hits10) / n,
        "mrr": sum(rr) / n,
        "top1_ci95": _bootstrap_ci(hits1, lambda v: 100 * sum(v) / len(v)),
        "_hits1": hits1,
    }


def _bootstrap_ci(per_case: list[float], fn, n_boot=10000, seed=0) -> list[float]:
    if not per_case:
        return [0.0, 0.0]
    rng = random.Random(seed)
    n = len(per_case)
    vals = []
    for _ in range(n_boot):
        vals.append(fn([per_case[rng.randrange(n)] for _ in range(n)]))
    vals.sort()
    return [round(vals[int(0.025 * n_boot)], 1), round(vals[int(0.975 * n_boot)], 1)]


# ── driver ─────────────────────────────────────────────────────────────────────
def run(rank_fn, cases, idx, pos, scope: str, seed: int, limit=None) -> dict:
    rows = []
    for c in (cases[:limit] if limit else cases):
        cid = c["scenario_id"]
        gt = c["scenario"]["ground_truth"]["target_guid"]
        pool = list(pool_candidates(c))
        if gt not in pool:
            continue
        cand = build_candidates(cid, gt, pool, idx, scope, seed)
        r = rank_fn(cid, cand, idx)
        rows.append({"case_id": cid, "gt": gt, "pool": len(pool), "n_cand": len(cand),
                     "rank": gt_rank(r["ranking"], gt), "chance": 1.0 / len(cand),
                     "is_filler": gt in pos, "valid_json": r.get("valid_json"),
                     "raw_output": (r.get("raw_output", "") or "")[:200]})
    all_ranks = [x["rank"] for x in rows]
    fill_ranks = [x["rank"] for x in rows if x["is_filler"]]
    chance1 = 100 * sum(x["chance"] for x in rows) / max(len(rows), 1)   # mean per-case Top-1 chance
    a = summarise(all_ranks); a.pop("_hits1", None)
    f = summarise(fill_ranks); f.pop("_hits1", None)
    return {
        "scope": scope, "rows": rows, "all": a, "filler": f,
        "top1_chance": round(chance1, 1),
        "mean_n_cand": round(sum(x["n_cand"] for x in rows) / max(len(rows), 1), 1),
        "valid_json_rate": round(sum(1 for x in rows if x["valid_json"]) / max(len(rows), 1), 3),
    }


def _print_scope(tag: str, res: dict):
    a, f = res["all"], res["filler"]
    print(f"\n=== {tag} | scope={res['scope']} | mean |cand|={res['mean_n_cand']} "
          f"| Top-1 chance={res['top1_chance']}% | valid-JSON={res['valid_json_rate']:.0%} ===")
    print(f"{'set':<10}{'n':>4}{'Top-1':>9}{'Top-10':>9}{'MRR':>8}   Top-1 95% CI")
    for name, s in (("all", a), ("filler", f)):
        print(f"{name:<10}{s['n']:>4}{s['top1']:>9.1f}{s['top10']:>9.1f}{s['mrr']:>8.3f}   {s['top1_ci95']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stub", action="store_true", help="lexical stand-in for the VLM (no Modal/GPU)")
    ap.add_argument("--scope", choices=["full", "siblings", "both"], default="both",
                    help="full pool (ladder), sibling shortlist (fine discrimination), or both")
    ap.add_argument("--seed", type=int, default=0, help="candidate-shuffle seed")
    ap.add_argument("--limit", type=int, help="only the first N cases (smoke test)")
    ap.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    a = ap.parse_args()

    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)

    if a.stub:
        rank_fn = stub_ranker({c["scenario_id"]: c for c in cases})
        tag = "stub (lexical, NOT the VLM result)"
    else:
        import modal
        predictor = modal.Cls.from_name(MODAL_APP, MODAL_RERANKER)()
        rank_fn = vlm_ranker(predictor, a.data_root)
        tag = "zero-shot Qwen2.5-VL (base, no adapter)"

    scopes = ["full", "siblings"] if a.scope == "both" else [a.scope]
    results = {s: run(rank_fn, cases, idx, pos, s, a.seed, limit=a.limit) for s in scopes}

    OUT.mkdir(exist_ok=True)
    (OUT / "vlm_reranker_baseline.json").write_text(
        json.dumps({"method": tag, "seed": a.seed, "scopes": results}, indent=2))

    print(f"\n############ VLM reranker baseline — {tag} ############")
    for s in scopes:
        _print_scope(tag, results[s])
    print("\nLedger rows for external_baseline.py figure:")
    for s in scopes:
        a60 = results[s]["all"]
        label = "zero-shot VLM\\n(full pool)" if s == "full" else "zero-shot VLM\\n(siblings)"
        print(f'  rows["{label}"] = '
              f'{{"top1": {a60["top1"]:.1f}, "top10": {a60["top10"]:.1f}, '
              f'"mrr": {a60["mrr"]:.3f}, "n": {a60["n"]}}}')
    print(f"\nfull dump → {OUT / 'vlm_reranker_baseline.json'}")


if __name__ == "__main__":
    main()
