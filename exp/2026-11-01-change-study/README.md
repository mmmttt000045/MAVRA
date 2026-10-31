# Fig. 6: eleven data changes against published agent memories (DeepSeek official API)

Redo of the 10-31 Fig. 6 study (`exp/2026-10-31-diverse-scenarios`), authorized by the
user on 2026-10-31 with a budget of about CNY 40. The earlier study had 1–3 questions
per change, one run, frozen controls from older code, and two MAVRA defects found in its
traces; its bars could not separate methods. This study fixes the defects, freezes a
larger bank, and runs every cell fresh with the same binary.

## Design (`protocol.json`, fixed before the first paid call)

- Schemas: synthetic retail (1M store-sales rows) and TPC-H SF1; metrics M1, M3, M5.
- Methods: SQL-adapted ACE and AWM, official G-Memory core (all through `memory-service.py`),
  and MAVRA `metric-global-full`. Same planner prompt for all; MAVRA adds its metric tools.
- One agent A learns each metric from two questions that state its business definition and
  a verified answer, then answers by metric name only; every question is a new conversation.
- Phases: held-out (unchanged data) and eleven changes, each from the original data and the
  method's post-held-out memory: non-breaking (append, backfill, correct, addcol), covered
  breaks (status, revision, dupload, dimhist, latekey), not covered (unit, mirror).
- Bank (`select-bank.py` on the model-free probe `metric-bench --bank-probe`): single-month
  and period-difference questions of every metric that reads a written table; 52 scored
  questions per synthetic cell and 40 per TPC-H cell, identical for all methods and runs.
  The probe also records the reference SQL's answer after each representation change.
- Feedback: every method sees its own last three results with binary correctness; no
  reference answers, SQL or change labels reach any method.
- Scoring: correct / clarification / wrong; clarification counts as not correct and is
  shown separately. Pooled accuracy per group, mean over runs, range over runs.
- Three runs per method. Run 1 used `--pool 8`; runs 2–3 ran concurrently with `--pool 4`
  (database connections per cell; agents issue one SQL statement at a time).

## Method changes before the study (main repository)

- Date-key repair (`repair_date_key`, `TimeSpec.key_alias`, `Check::KeyAliasCoverage`,
  `Check::KeyAliasUnique`): when date coverage fails, try `yyyymmdd` and day-number
  encodings over the date dimension's date columns; adopt exactly one encoding that is
  unique with the dimension key and restores coverage; compile a union-extended date
  dimension. Integration test `postgres_date_key_repair`; the change-scenario test now
  expects repaired revisions on latekey.
- Consumer rule: a `run_metric` result has passed the definition's conditions on the
  query's snapshot and is submitted as is; when facts cannot be assigned to a period and
  the data do not say which, ask for clarification.
- Repair notices: after a repair is published, the revocation notice to earlier consumers
  is replaced by one that names the new revision (the smoke test showed the stale notice
  made an agent ask for clarification despite a valid repaired result).
- Published-memory bridge (`paper-*` modes), frozen `--bank`, `--bank-probe`, per-task journal.

## Execution record

- Smoke test (synthetic, 9 tasks per method, `bank-synthetic-smoke.json`): CNY 0.52,
  189 calls, no errors; found the repair-notice defect above.
- Independent read-only review of the harness before the first paid run; fixes: pilot stop
  rule, per-cell completion checks (bank match, denied requests, database cleanup),
  provenance (HEAD, binary sha256), balance-check fallback, empty-phase guard.
- Run 1 (pilot, 8 cells): complete, CNY 9.02, no API errors; no harness defect found, so
  run 1 is part of the study. Runs 2–3 ran concurrently: all 16 cells complete.
- Total: 24 cells, 1,104 scored answers and 144 learning tasks, 7,889 official API calls,
  CNY 27.53 charged (account decrease 27.50) plus 0.52 for the smoke test; 0 API errors.
  Raw reports, completion records and the usage ledger: `raw-results.tgz`.

## Results (three runs; pooled over both schemas, mean and run range)

| Group | MAVRA | ACE | G-Memory | AWM |
|---|---:|---:|---:|---:|
| Held-out (unchanged data) | 100.0 | 100.0 | 86.1 | 83.3 |
| Non-breaking updates | 100.0 | 95.2 | 67.9 | 69.0 |
| Covered breaks | 87.7 [87–89] | 66.7 | 57.0 | 49.1 |
| Not covered (unit, backup copy) | 26.2 | 71.4 | 52.4 | 40.5 |

- Covered breaks, synthetic retail: MAVRA 97.0% (latekey 18/18 through the date-key repair,
  dupload 16/18); baselines 40.9–68.2%. TPC-H: MAVRA 75.0% plus 12/12 clarification
  requests on the late batch whose ship dates are NULL (no method can reach the reference);
  G-Memory 75.0%, ACE 64.6%, AWM 60.4%. MAVRA's wrong answers on covered breaks: 1.8%
  (baselines 33–51%).
- MAVRA uses the fewest tokens in every group of both schemas (17.8k per question overall,
  baselines 32.9–47.2k).
- Weaknesses kept in the paper: on changes the conditions do not cover, MAVRA serves the
  still-valid definition while recomputing agents adapt to the binary feedback; on TPC-H
  breaks the repair search over 6M line items makes MAVRA's sessions slower (124 s vs at
  most 23 s per question).
- Per-change counts for every method and run: `summary.md`, `study-stats.json`.
- Binary for all runs: sha256 `67e2fc83b7a5…` built at `96da0bc`.

## Reproduce the aggregation

```
python3 exp/2026-11-01-change-study/analyse.py --results results/change-study-20261101
python3 tools/figures/build.py change-study
```

`analyse.py` writes `study-stats.json`, `summary.md` and `overleaf/gen/change-study.tex`;
the figure script checks every plotted accuracy against the macros.
