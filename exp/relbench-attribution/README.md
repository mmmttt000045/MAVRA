# Three-Run RelBench Evaluation and Cutoff-1 Refitting Attribution

**Paper Reference:** §6.5 (*Q4: Predictive Feature Reuse Across Tasks and Cutoffs*), Table 5.

## Overview

This directory archives the repeated multi-run evaluation and attribution controls for RelBench predictive feature reuse:

1. **Three-Run Repeated Evaluation** ([gate-r1.json](gate-r1.json), [gate-r2.json](gate-r2.json), [gate-r3.json](gate-r3.json)): Per-run completion, zero-leakage audit verification, quality, and token-efficiency gates across `rel-stack` and `rel-trial`.
2. **Cutoff-1 Frozen-SQL Refitting Control** ([frozen-rel-stack.json](frozen-rel-stack.json), [frozen-rel-trial.json](frozen-rel-trial.json), [frozen-summary.json](frozen-summary.json)): Evaluates refitting LightGBM at cutoffs 2–5 on the unmodified cutoff-1 feature SQL without agent refinement, isolating pure temporal refitting from online feature adaptation.
3. **Temporal Shift & Reuse Anatomy Attribution** ([shift-attribution.json](shift-attribution.json)): Per-task mean and run-to-run spread across cutoffs 1–5 alongside refit success and candidate-addition acceptance rates.

## Reproduction

- **Summarize frozen-SQL refitting gains offline**:
  ```bash
  python3 tools/relbench/frozen-summary.py exp/relbench-attribution/frozen-rel-*.json
  ```
- **Regenerate RelBench Table 5 macros**:
  ```bash
  python3 tools/relbench/paper-stats.py --out results/gen
  ```
- **Re-run frozen cutoff-1 refitting on PostgreSQL** (`MAVRA_DB_URL`):
  ```bash
  python3 tools/relbench/frozen-program.py \
    --data results/relbench-data/rel-stack \
    --prep results/relbench-data/rel-stack-prep \
    --template relbench_stack_t1 \
    --runs results/relbench-run/mavra-r1 \
    --out results/frozen-rel-stack.json
  ```
