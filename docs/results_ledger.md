# RESULTS LEDGER

> Every reported number lands here, once, with provenance. If a number isn't in this
> ledger it doesn't go in the paper. Append-only; never silently edit a past row.

Conventions:
- **Always** report bootstrap 95% CI for rate metrics (n is small).
- Mark each row **confirmatory** (pre-registered in that phase's `protocol.md`) or
  **exploratory** (post-hoc).
- `run_id` ties back to `output/<run_id>/` and the git `commit` it was produced at.

---

## Baselines / thesis-carried numbers (for reference, AP held-out n=60)

| metric | value | source |
|---|---|---|
| oracle GT-in-Pool | 100% | thesis Table 7.1 |
| oracle Top-10 (L3) | 58.3% | thesis Table 7.1 |
| oracle Top-10 (L4) | 100% (58.3% cov) | thesis Table 7.1 |
| realized GT-in-Pool | 100% | thesis Table 7.2 (G8) |
| realized Top-10 | ~30% | thesis Table 7.2 (G8) |
| realized Top-1 | ~6.7% | thesis Table 7.2 (G8) |
| realized MRR@10 | ~0.11 | thesis Table 7.2 (G8) |
| realized median pool | ~76 | thesis Table 7.2 (G8) |

> These are carried from the thesis for orientation only. Re-run on this repo's harness
> before citing as "our system" numbers (toolchain/version may differ).

---

## Run log

| date | phase | run_id | commit | test set (n) | metric | value | 95% CI | conf/expl | notes |
|---|---|---|---|---|---|---|---|---|---|
| _(first row added when `run_benchmark.py` produces a result)_ | | | | | | | | | |
