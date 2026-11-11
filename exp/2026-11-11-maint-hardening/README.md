# Maintenance hardening, closest simple baseline, and unseen-binding accuracy (2026-11-11)

Motivation: a mock PVLDB review (user, 2026-11-11) asked three things the current evidence does
not answer. (1) What does MAVRA add over the closest simple scheme (shared parameterized
definitions, the same basic checks, invalidate on failure)? (2) Why does a repair that restores
the structural conditions and reproduces the source answer preserve the business meaning, and on
which snapshot is the source answer reproduced? (3) Table VI reports 3 wrong answers among
covered breaks while the abstract says zero wrong.

Diagnosis before any change (`exp/2026-11-01-replay-rerun/rerun-final-reports.tgz`, code):

- The 3 wrong answers are TPC-H `q12_b0_lineitem` on `latekey`. Its time attribution is
  `l_receiptdate` (coverage passes), but its filter has `l_shipdate < l_commitdate`; the late
  batch has NULL `l_shipdate`, so the filter is UNKNOWN on those rows and drops them silently.
  No derived condition covers NULLs in filter or measure columns.
- Repro (G8) runs the repaired definition and the agent's verified SQL on the learning-time
  snapshot (`g8_snapshot` in replay, `g8_snapshot_db` in metric-bench). It never sees post-update
  data, so an edit such as `i_is_current = 'Y'` is a no-op there and always passes.
- All 115 wrong answers in "premise changes" come from `unit`: an UPDATE that multiplies money
  columns by 100 from month 7 of the holdout year. The paper says such shifts leave no data trace;
  they do leave a distributional one.

Everything below is fixed before the first run. Fixes A and C come from error analysis of the
same replay data, so the paper must say so and report the earlier 804/3/33 next to the new
numbers. B is tested on a new update class (`reclass`) that was designed together with B, before
any run; it is the held-out test for B.

## A. Row-loss conditions for predicate and measure columns (`Check::NotNull`)

- Derivation: every column that the definition's filters (definition and join filters, any
  table) or its measure reference, except the time column (covered by the coverage condition)
  and join keys (covered by join completeness). Condition: non-null fraction of the column's
  table; publication baseline b; accept iff null fraction <= b + 0.1 pp (the coverage tolerance).
- Not in the restricted repair space: a failure withholds the definition.
- Prediction: the 3 `tpch/latekey` q12 instances move from served-wrong to withheld; no other
  instance changes class; zero new withholdings on the 534 non-breaking instances.

## C. Measure-scale condition (`Check::MeasureScale`)

- Derivation: every numeric fact column referenced by the measure. Statistic: per month of the
  definition's time attribution, the median of |value| over non-null, non-zero values, months
  with at least 30 such rows. Publication baseline [lo, hi] = min and max monthly median.
  Accept iff every month lies in [lo / 5, hi * 5]. K = 5 is fixed here.
- A failure withholds the definition and asks for business confirmation (B2 is a premise; the
  data can show that it may have changed, not what the new unit is).
- Prediction: `unit` instances whose measure reads a scaled money column move from served-wrong
  to withheld; non-breaking instances unchanged. Any false withholding is reported as is.

## B. Answer-preserving repair admission (gate G9)

- After G8, compare the candidate revision on the current snapshot with the previous revision on
  the last validated snapshot (the learning snapshot in both harnesses), per time bucket (the
  fact's date key, or the date for date-column calendars). Only buckets whose fact rows are
  unchanged are compared: fingerprint = row count and sum of `hashtext` over the fact columns the
  previous revision reads (joined along the time path when the date lives on another table).
- Any bucket whose value differs (task precision) rejects the repair: the definition is withheld
  and the reason names the number of moved buckets. If no bucket is unchanged the gate is vacuous;
  this is recorded and the repair stands on G8 alone.
- Guarantee to state in the paper: an admitted repair never changes a previously computable
  answer whose fact rows did not change. It does not decide a business choice the data cannot
  distinguish; such repairs are withheld when the history shows the difference.
- New update class `reclass` (premise change, on the `dimhist` target table): for one third of
  the keys, a history row keeps the current attribute (`is_current = 'N'`) and the current row
  takes the other attribute, i.e. a real reclassification under a type-2 history. Gold:
  sale-time (as-of) attribution, which equals the answer before the change. A "current
  attribution" reading would give a different answer; the correct system behavior is to serve
  the as-of answer or to withhold. We also report how many served answers equal the
  current-attribution reading.
- Predictions: before B, MAVRA repairs `reclass` with `is_current = 'Y'` and serves wrong answers
  for definitions that filter on the attribute; with B those are withheld; definitions that do
  not read the attribute keep a correct repair. `dimhist` (current row unchanged) keeps its
  repairs (G9 passes).

## Replay run (A + B + C, no model calls)

Four schemas as in Table VI (TPC-DS SF1 hand-written changes; TPC-H SF1, SSB, BIRD financial
spec-driven), condition policy, snapshot oracle, all eleven archived changes plus `reclass`.
The other policies run `reclass` only; for the eleven archived changes they keep their archived
outcomes (they share no code with A–C). Ablation cells: MAVRA without B on `dimhist` and
`reclass` (flag `history_check = false`). Outputs: per-change counts, the new Table VI, and every
MAVRA instance whose class differs from the 11-01 final run.

## D. Closest simple baseline, end to end (change study)

Protocol, banks, prompts, model, feedback and scoring of `exp/2026-11-01-change-study`, both
schemas, three runs. Arms:

- MAVRA, new binary (`metric-global-full`, i.e. with A–C).
- Shared recheck (`metric-global-recheck`): identical to `metric-global-full` except
  `Maint::Definition` (every condition of an affected definition reruns on first use after a
  write), no cross-definition sharing of condition results (`cond_reuse = false`), and no repair
  (`repair = false`: a failing definition is withheld and the agent explores on its own).
  It uses the same derived condition set C(m), including A and C.

ACE, AWM, G-Memory and TeCoD keep their archived cells (same banks, prompts, model). Report per
group: correct / wrong / clarification, tokens and seconds per question, and validation database
time. Budget cap CNY 15 for D. Stop rule: no redesign after the formal cells start.

Predictions: on non-breaking updates both arms answer correctly; Shared recheck spends more check
time. On covered breaks Shared recheck withholds, its agents explore from scratch: more tokens and
time, accuracy as good as the agent's own exploration (baselines reached 49–69%).

## E. Unseen-binding accuracy of published definitions (C1, no model calls)

Inputs: the MAVRA-family cells of `results/scen-20260930` and `results/scen-20261010` on noctis
(the 664 judged sessions of Section 6.6), synthetic retail with 1M store-sales rows, v1 data.
For every distinct published definition (status Valid) and every G7-rejected draft, compile all
36 single months of 2000–2002 and the three full years (39 bindings) and compare with the
benchmark's reference answer (`metricbench::gold_sql`) at task precision.

Report: share of published definitions exact on all 39 bindings; per-binding accuracy; for each
G7-rejected draft, the share of bindings it would have answered wrongly (the counterfactual
without G7). If a published definition fails on some binding, report it and its cause; a
multi-binding replay gate is then a candidate change for a later, separately registered run.
