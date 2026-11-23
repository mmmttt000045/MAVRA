# Value Guards, Historical Repair Gate G9, Unseen Bindings, and Sustained Writes

**Paper Reference:** §4.1, §4.4, §6.3 (Table 3), §6.4 (Table 4), and §6.6 (Table 6).

## Overview

This directory contains six evaluations covering value-distribution guards, historical repair admission, serving-vs-withholding decomposition, unseen temporal bindings, 26-definition lookup confirmation, and sustained read/write concurrency:

1. **12-Change Replay & Historical Gate `G9` Ablation** ([replay-guards.json](replay-guards.json), [analyse-replay.py](analyse-replay.py)): Evaluates `NotNull` and `MeasureScale` value conditions plus untouched-bucket historical check `G9` across all four schemas and 12 update types (including historical category reclassification `reclass`), reducing served-wrong answers across common instances to `0`.
2. **Serving-vs-Withholding & Template Decomposition** ([served-split.json](served-split.json), [served-split.py](served-split.py)): Decomposes end-to-end schema-evolution outcomes (Table 4) into served-definition answers ($y_j = 1$) vs. withheld fallback exploration ($y_j = 0$) across `MAVRA`, `Shared recheck`, `Template + schema check`, and `Template + write invalidate`.
3. **Unseen Parameter Bindings** ([binding-report.json](binding-report.json), [binding-macros.py](binding-macros.py)): Evaluates 387 published definitions across 39 unseen temporal parameter bindings (`binding-bench`), contrasting `G7`-admitted definitions against `G7`-rejected over-specialized SQL.
4. **26-Definition Lookup Confirmation** ([lookup-confirm/confirm-summary.json](lookup-confirm/confirm-summary.json), [lookup-confirm/confirm.py](lookup-confirm/confirm.py), [lookup-confirm/measure_gen.py](lookup-confirm/measure_gen.py)): Consumer-agent confirmation turn on uncertain (`refer` / `similar`) replies and phrasing-generation cost measurement.
5. **Cross-Generator Paraphrases & 26-Definition Baselines** (`lookup-glm/`, `lookup-tecod/`): 174 human-validated cross-generator paraphrases of the 96 core requests ([lookup-glm/requests-paraphrased.json](lookup-glm/requests-paraphrased.json)), full-catalog LLM judge summary ([lookup-glm/baselines-summary-glm.json](lookup-glm/baselines-summary-glm.json)), and 26-definition TeCoD summary ([lookup-tecod/tecod-summary.json](lookup-tecod/tecod-summary.json)).
6. **Sustained Concurrent Writes** ([sustained/summary.json](sustained/summary.json), [sustained/macros.py](sustained/macros.py)): 64-session concurrent workload across four write-rate regimes (`0/1`, `1/8`, `1/2`, `2/1`) plus statement-level `mavra_versions` trigger overhead.

## Reproduction

- **Offline LaTeX macro generation** (no database or API key required):
  ```bash
  python3 exp/maintenance-guards/analyse-replay.py --tex results/gen/replay-guards.tex
  python3 exp/maintenance-guards/served-split.py --tex results/gen/served-split.tex
  python3 exp/maintenance-guards/binding-macros.py --tex results/gen/binding.tex
  python3 exp/maintenance-guards/sustained/macros.py --tex results/gen/sustained.tex
  ```
- **Live PostgreSQL benchmarks** (`MAVRA_DB_URL` / `MAVRA_TEST_DB_URL`):
  ```bash
  ./target/release/mavra --out results/binding binding-bench \
    --defs exp/population-sharing/tpcds-defs.json
  cargo test --release --locked q5_bench_tests::postgres_sustained_writes \
    -- --ignored --nocapture --test-threads=1
  ```
