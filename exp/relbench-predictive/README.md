# Cross-Cutoff Predictive Feature Reuse on RelBench

**Paper Reference:** §6.5 (*Q4: Predictive Feature Reuse Across Tasks and Cutoffs*), Table 5.

## Overview

This directory contains the aggregated session metrics and cold-start vs. reuse work breakdowns for **RelBench** entity-level predictive feature engineering across **5 sequential temporal cutoffs** on two relational databases:

- **`rel-stack`** (Stack Exchange network: `user-engagement`, `user-badge`, `post-votes`)
- **`rel-trial`** (ClinicalTrials.gov: `study-outcome`, `study-adverse`, `site-success`)

Every method interacts with PostgreSQL under identical tool budgets, fixed downstream **LightGBM 4.6.0** hyperparameters, and a mandatory row-level temporal leakage audit before any feature table is scored.

### External Baseline Protocol Notes

All baselines share the exact same PostgreSQL schema, planner model (`deepseek-flash`), stopping rule, LightGBM learner, and row-level temporal leakage audit (`tools/relbench/harness.py`):

- **`ACE`** (Zhang et al.; vendored Apache-2.0 prompts/utils in `third_party/ace/`): Uses `REFLECTOR_PROMPT_NO_GT` and `CURATOR_PROMPT_NO_GT` (80k token playbook budget, one Reflector + Curator pass per session, temperature 0) with validation-score execution feedback and strictly sequential temporal cutoffs (no future-label multi-epoch adaptation).
- **`G-Memory`** (Zhang et al.; adapter in `tools/relbench/gmemory_service.py`): Preserves the three-tier insight/query/interaction hierarchy (`successful_topk=1`, `insights_topk=5`, `all-MiniLM-L6-v2`) with domain prompt overrides for relational feature engineering and validation-beat-reference success labels (`Resolved`).
- **`AWM`** (Wang et al.; vendored Apache-2.0 prompts in `third_party/awm/`): Online workflow induction after each cutoff session exceeding the entity-table reference, sampling one verified trajectory per task template (`max_tokens=2048`, non-reasoning mode so full workflow text fits budget).
- **`TeCoD`** (Jivani et al.; adapters in `tools/relbench/tecod_service.py` and `tools/relbench/tecod_server.py`): Uses released `Qwen/Qwen3-Embedding-4B` + `smitxxiv/Qwen3-Re4B-SQL-TeCoD-TMM` NLI template selection (`sgc` prompt-guided mode for API LLMs, top-3 cosine ICL examples) over online-admitted clean feature SQL templates.
- **`FeatPilot*`** (Liang et al.; implemented in `tools/relbench/featpilot.py`): LLM-free BFS relational feature discovery ($U_G = \mathrm{FI} \times \mathrm{IQ}$, $T_{\mathrm{IQ}}=0.1$, heap $H=30$, budget $B=10$) adapted to PostgreSQL primary/foreign-key graphs with `LATERAL` `seed_time` temporal bounding on every joined table.

## Curated Files

- [paper-sessions.json](paper-sessions.json) — Per-session validation/test scores, token usage, database execution times, and audit outcomes across all evaluated baselines.
- [reuse-work-data.json](reuse-work-data.json) — Cold-start vs. cross-cutoff reuse tool-call breakdown (plotted by `tools/figures/reuse_work.py` and `tools/figures/relbench_cumulative.py`).

## Reproduction

1. **Prepare RelBench PostgreSQL template databases** (`MAVRA_DB_URL`):
   ```bash
   python3 tools/relbench/prepare.py --data results/relbench-data/rel-stack \
     --out results/relbench-data/rel-stack-prep --cutoffs 5 \
     --pg "$MAVRA_DB_URL" --dbname relbench_stack_t1
   python3 tools/relbench/prepare.py --data results/relbench-data/rel-trial \
     --out results/relbench-data/rel-trial-prep --cutoffs 5 \
     --pg "$MAVRA_DB_URL" --dbname relbench_trial_t1
   ```
2. **Run a RelBench evaluation arm**:
   ```bash
   python3 tools/relbench/harness.py --arm mavra-retry --run 1 \
     --data results/relbench-data/rel-stack \
     --prep results/relbench-data/rel-stack-prep \
     --template relbench_stack_t1 --out results/relbench-run/mavra-r1
   ```
3. **Regenerate Table 5 (`Rb*` macros and `relbench-table.tex`) offline**:
   ```bash
   python3 tools/relbench/paper-stats.py --out results/gen
   ```
