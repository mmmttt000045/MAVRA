# RelBench Multi-Run Evaluation and Cutoff-1 Refit Attribution

This directory archives the three-run `MAVRA` (`mavra-retry`, `v10-plan.json`) and three-run `No memory` (`none-repeats-plan.json`) evaluations reported in Table 3, Figure 6, and Figure 7 of the PVLDB manuscript, together with the pure cutoff-1 refit attribution (`frozen-rel-stack.json`, `frozen-rel-trial.json`, `frozen-summary.json`, `explain-v10.json`).

## Files

- `v10-plan.json`, `none-repeats-plan.json` — execution configurations for the three identical-input `MAVRA` and `No memory` runs on `rel-stack` and `rel-trial`.
- `gate-v10-r1.json`, `gate-v10-r2.json`, `gate-v10-r3.json` — per-run session cost, validity, and held-out test metrics across all 30 sessions per run.
- `frozen-rel-stack.json`, `frozen-rel-trial.json`, `frozen-summary.json` — pure cutoff-1 refitting baseline (refitting the cutoff-1 program at cutoffs 2–5 with zero agent turns).
- `explain-v10.json` — per-task decomposition separating cutoff-1 starting quality from cutoffs 2–5 adaptation (`tools/relbench/explain-quality.py`).

## Regeneration

```bash
python3 tools/relbench/paper-stats.py --out overleaf/gen
python3 tools/relbench/reuse-work-data.py
python3 tools/relbench/frozen-summary.py
python3 tools/relbench/explain-quality.py
```
