# STATUS — where we are (at a glance)

> Single-page progress view. Updated as work lands. Detail lives in
> [`ROADMAP.md`](ROADMAP.md) (plan), [`results_ledger.md`](results_ledger.md) (numbers),
> [`DATA_INVENTORY.md`](DATA_INVENTORY.md) (assets), and `git log` (timeline).

**Last updated:** 2026-06-09
**Current position:** Phase 0 — step 1 (contract done), step 2 Idea 3a **first + second cut done** (Idea 3b retired by the 2nd-cut gate); live-closeout prepped (blocked on Docker).

---

## ✅ Done

- **Clean monorepo scaffold + docs** — `aec-interpreter`, src-layout, docs/ (commit `9ec5707`).
- **Code + asset migration** — `src/aec_interpreter/{neurosym,visual,common,handoff,schema,evaluation_infra}` + `ifc_engine`, `pipeline_base`; imports rewritten; reranker closure recovered from old eval tree (`6a4ee03`, `b87ef4b`).
- **Installable env (uv)** — `uv venv` + `uv pip install -e ".[dev]"`; 42/43 modules import clean (only `common.mcp` = V1/`[agent]`, expected).
- **Offline eval harness** — `eval/run_benchmark.py --from-traces` (+ `--variant`, `experiments.yaml`), clean scorer + bootstrap CIs (`3e2ca8c`).
- **Thesis parity validated** — G8 reproduces all 7 Track-B metrics exactly (Top-10 30.0%, MRR 0.1104, GT-in-pool 100%, pool median 76 / mean 118.4).
- **Parity regression test** — `tests/test_parity.py`, `pytest` 4 passed (`ab51520`).
- **Per-field confidence contract (structure)** — `schema/contract.py`: uniform
  `FieldValue {value, confidence, source, role}` + `ConstraintContract` + `from_legacy`
  adapter + generated `schemas/constraint_contract.schema.json` + 5 tests. (§2.1 step 1)
- **Idea 3a first cut (attribute-layer ceiling, Neo4j-free)** — `eval/fingerprint_ceiling.py`:
  median pool 46→13 (3.8×) from attributes alone, all via `object_type`; plateaus (2/60
  unique) → motivates topology + P1. Figure + ledger + 2 tests. (§2.1 step 2)
- **Idea 3a second cut (topology + reliability-weighting, Neo4j-free)** —
  `eval/fingerprint_reliability.py`: topology adds only 13→**12** (FILLS/CONNECTS
  homogeneous, ADJACENT_TO sparse) → feature space **saturated**; ∏r recall collapses to
  0.009 if all hard-filtered (best single r=0.625) → the 76→~13 gap is **reliability-bound**.
  **Decisive gate: Idea 3b (learned feature-selector) = SKIP; all effort → P1 calibrated
  routing.** Calibrated `object_type` routing alone: coarse 46→25.4. Figure + ledger + 3 tests.
  Also: full `IfcRel*` census (no untapped relation; `IfcRelSpaceBoundary`=0 → room-feature
  is the real-data revisit target) + 2-lever correction (soft rerank, not hard filter).
- **Idea 3a third cut (soft-rerank prize on Top-k/MRR, offline)** — `eval/rerank_prize.py`:
  reranks the real trace pools by feature agreement. Coarse is saturated (oracle storey+class
  31.5 ≈ realized 30); the prize is **object_type** — realistic specialist (r=0.625) +
  calibrated soft rerank **≈ doubles Top-10 (30→59.5) and Top-1 (6.7→13.2), zero recall cost**.
  Money figure for the paper; justifies P2→P1 order. Figure + ledger + 4 tests (18 total).
- **Live-closeout prep (docker-independent)** — `docker-compose.yml` (Neo4j 5.26, no APOC), `scripts/graph_build/` (01 export / 02 topology / 03 views) + runbook, AP IFC model + element_index migrated, `config/config.yaml`, py2neo dep (`1a9487a`).

## 🟡 In progress / partial (§2.1 step 1)

- **Per-field confidence contract** — ✅ structure + adapter + schema + tests done; ⬜ still
  need to *populate* it in the live extractor/specialists (P1 wiring) once `--live` exists.
- **Larger held-out (n≈300)** regenerated from `synth_v0.5_ap` — NOT done.
- **Leakage-safe split** (disjoint elements/regions) — NOT done.

## ⬜ Next (§2.1 order)

1. finish step 1: confidence contract → n≈300 held-out → leakage split.
2. **step 2 — Idea 3a** offline optimal-fingerprint ceiling (`eval/fingerprint_ceiling.py`) — highest ROI, reframes the paper.
3. step 3 — P2 gated specialists (+ Idea 2a storey/zone segmenter).
4. step 4 — P1 calibrated routing (ECE gate) → step 5 adaptivity ablation → step 6 P4.

## ⚠️ Blockers

- **Docker** WSL integration off → can't run Neo4j → can't run `--live` / ingest / retire `mscd_demo`. Runbook is ready; needs Docker Desktop WSL integration enabled (or a local Neo4j on `bolt://localhost:7687`, `neo4j/password`).

## 🚪 Publish gate (retire `mscd_demo`)

Requires `--live` self-contained: Neo4j up → `scripts/graph_build` 01→03 → `--live` reproduces frozen G8. Then old repo can be frozen/closed.
