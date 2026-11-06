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

## Final-binary MAVRA cells (2026-11-01, used in the paper)

After the first study, TPC-H breaks were slow for MAVRA (124 s per session against at most
23 s): the duplicate load writes exact copies, so the grain-filter search over 6.3M line items
failed (8–16 `count(distinct …)` queries per definition, repeated for each definition), and the
agent then wrote its own deduplicating SQL. The main repository fixed this before the rerun
(commits 8db523b–de69b83): hash-aggregate key checks; a value-count prescreen in the filter
search; failed and ambiguous searches recorded per table version and reused; a new restricted
repair for exact duplicates (`Metric.dedup`, `Check::DistinctKeyUnique`); fact filters
qualified so that equivalent filters share one condition. Unit and integration tests pass
(the change-scenario test now expects repaired revisions on duplicate loads).

- Smoke test (TPC-H, `bank-tpch-smoke.json`, 7 scored tasks): all correct, CNY 0.16; the
  first answer after the duplicate load took 30 s (was 500–861 s).
- Formal rerun: MAVRA only, runs 1–3 on both schemas, six cells concurrently with `--pool 4`,
  cap CNY 6.0; HEAD fdf56be, binary sha256 `3ec110d060fe…`; 1,104 API calls, CNY 2.33, 0
  errors (`results/change-study-20261101-final`). The baseline cells are those of the first
  study (same banks, prompts, model, and machine); they ran 10-31 night with 8–16 concurrent
  cells, the MAVRA cells 11-01 midday with six.
- The final repository (d648f3d) additionally filters deduplicated facts by the period's date
  keys before DISTINCT; answers are identical, only deduplicated queries over a date dimension run
  faster, so the MAVRA times above are conservative.
- Aggregation: `analyse.py --results results/change-study-20261101 --arm-results
  mavra=results/change-study-20261101-final` (the paper's Fig. 6 and Cs* macros).

| Group (both schemas) | MAVRA | ACE | G-Memory | AWM |
|---|---:|---:|---:|---:|
| Held-out | 100.0 · 11.8k · 3.9 s | 100.0 · 15.1k · 4.3 s | 86.1 · 23.8k · 9 s | 83.3 · 25.6k · 13 s |
| Non-breaking | 100.0 · 11.7k · 4.8 s | 95.2 · 24.7k · 11 s | 67.9 · 44.3k · 23 s | 69.0 · 42.4k · 25 s |
| Covered breaks | 89.5 [89–89], 0 wrong · 11.9k · 7.0 s | 66.7 · 38.4k · 20 s | 57.0 · 45.1k · 25 s | 49.1 · 48.5k · 35 s |
| Not covered | 26.2 · 30.4k · 21 s | 71.4 · 49.5k · 27 s | 52.4 · 66.4k · 37 s | 40.5 · 71.4k · 52 s |

(accuracy % · tokens per question · mean session seconds). MAVRA has the fewest tokens and the
lowest mean session time in every group of both schemas; on held-out questions its time ties
ACE. Covered breaks: synthetic 66/66 correct; TPC-H 36 correct and 12 clarification requests
on the late batch without ship dates (every baseline answers those 12 wrongly). Not covered:
backup copy 11/12 (best of all methods; ACE 10/12), unit change 0/30 (ACE 20/30). Raw reports,
journals, completion records and the usage ledger of these cells: `raw-results-final.tgz`. The
earlier MAVRA cells (old binary) stay in `raw-results.tgz` and the tables above this section.

## Reproduce the aggregation

```
python3 exp/2026-11-01-change-study/analyse.py --results results/change-study-20261101
python3 tools/figures/build.py change-study
```

`analyse.py` writes `study-stats.json`, `summary.md` and `overleaf/gen/change-study.tex`;
the figure script checks every plotted accuracy against the macros.

## TeCoD as a fifth method (2026-11-06/07)

User 2026-11-06: TeCoD (SIGMOD 2026) joins the RelBench comparison, so it also joins this study. Protocol addition
`addition_20261106`: same banks, planner prompt, feedback, model and budget relay as the other methods; selection by
`tools/relbench/tecod_server.py` (released TeCoD template selection, one pool per cell, models loaded once); the memory
service's TeCoD actor puts the matched template and three examples before a repeated question (released order) and adds a
pair after a correct answer, using the SQL that produced the answer (`tecod_pair_sql`: the executed query named by the
derivation, or the derivation over several queries as scalar subqueries; 664 of 665 correct baseline answers of the
first study resolve this way). The pool is snapshotted after held-out and restored before every change.

- Binary: rebuilt for mode `paper-tecod` at 9deec9e (sha256 `ac454316…`). Since the baseline cells' binary the Rust changes
  touch only MAVRA's definition maintenance (8db523b, de69b83, fe961b7); the agent side (`metricbench.rs` planner, tools,
  bridge) is unchanged apart from the mode name.
- Review before the paid run (independent, read-only): must-fix items fixed (rebuild; pool SQL from the derivation instead
  of `final_answer.sql`; launch only after the RelBench TeCoD round had freed memory); a failed pool addition no longer ends
  a cell; analyse.py decides complete runs by the protocol's methods.
- Smoke (`results/change-study-20261106-tecod-smoke`, both schemas, smoke banks): both cells complete, 0 API errors,
  CNY 0.13.
- Formal (`results/change-study-20261106-tecod`, cap CNY 12): runs 1-3 started together at 04:15 with six cells sharing one
  selection server. Selection is CPU-bound (two 4B models in float32) and was the bottleneck (160-230 s wait per question
  for the agent's 5-30 s), so at 05:15 the run-2 and run-3 cells were stopped (before any result was looked at; their
  partial cells stay in the results directory, marked incomplete) and run 1 continued alone. Runs 2-3 are rerun afterwards.
- Aggregation while TeCoD has fewer runs: `analyse.py --results results/change-study-20261101 --arm-results
  mavra=results/change-study-20261101-final --arm-results tecod=results/change-study-20261106-tecod --partial-arm tecod`
  (the four methods keep their three runs; `arm_runs` and the macro `CsTecodRuns` record TeCoD's).
