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

## Results

### E. Unseen-binding accuracy (2026-11-11, noctis, HEAD 89322f2, `binding-report.json`)

68 MAVRA-family cells of `scen-20260930` and `scen-20261010`; synthetic retail, 1M store-sales rows, v1 data;
39 bindings per definition (36 single months 2000-01..2002-12 and three full years); task precision (2 decimals).

| Class | distinct definitions | publications / sessions | exact on all 39 bindings | wrong binding checks |
|---|---:|---:|---:|---:|
| Published (Valid) | 100 | 445 | 100 | 0 of 3,900 |
| G7-rejected drafts | 7 | 8 | 0 | 273 of 273 |

- Published definitions are diverse (46 distinct M3 return-rate formulations alone; COALESCE, qualified and
  unqualified columns, ratio orders), and every one matches the hand-written reference on every binding.
- Every G7-rejected draft is wrong on every binding: M5 drafts that drop the Electronics filter return about
  5x the reference (e.g. 12.66M vs 2.58M for 2000-02); M3 drafts that use the wrong denominator return about
  60% instead of about 24%; one M3 draft does not execute. Without G7 these drafts would have been published
  and served to every later agent.
- Scope: one synthetic schema with five metrics, period bindings only (no attribute slices), unchanged data.
  The result shows that, on this workload, G7's single-binding test did not let a lossy extraction through;
  it does not prove equivalence in general.

### Review point 4: lookup in one metric, with the confirmation turn (`lookup-confirm/`)

Input: the end-to-end first-ask replies of `exp/2026-11-10-lookup-facets/results-ft/serve-ens3/responses-first.jsonl`.
`confirm.py` lets deepseek-flash (official API) read each reply that needs confirmation (18 refer, 4 similar) and
name the definition(s) it means; nothing else changes.

- First response, set-exact (references counted as the returned set): 88/96 (91.7%). Refer replies carry 1.6
  candidates on average; 16 of 18 contain the gold set, the other 2 are absent requests.
- After confirmation: 22/22 confirmations correct; final set-exact 95/96 (99.0%), equal to the full-catalog LLM judge
  (190/192); all 17 absent requests end rejected. The remaining error (f12) is a direct answer (D13+D14 for D13).
- Cost per request, confirmation included: 0.53 s and 89 LLM tokens (56 prompt + 33 completion), against 2.16 s and
  1,534 tokens for the full-catalog judge.
- Repeated phrasing (alias table): first response set-exact 94/96 in 33 ms.

### Review point 6: lookup training cost (`lookup-confirm/measure_gen.py`, `measure-gen.out`)

Six generation calls re-issued with the pilot's prompt and settings (PER=15, thinking on, effort low): 246 prompt and
3,423 completion tokens per call. The training set took about 510 calls (five batches of 98 intents + 4 absent-metric
calls), so about 1.9M tokens. Training: 1,912 s per judge, three judges (1.6 GPU-hours, shared RTX 5880 Ada).
Against the full-catalog judge (1,534 tokens per lookup) MAVRA saves 1,445 tokens per lookup: payback after about 1.3k lookups.

### Review point 5: RelBench per cutoff (`exp/2026-10-20-relbench/paper-sessions.json`, no new runs)

user-badge AUC, MAVRA vs No memory, cutoffs 1-5: 0.8195/0.8458, 0.8205/0.8501, 0.8375/0.8550, 0.8569/0.8800,
0.8379/0.8632 (behind at every cutoff, by 0.018-0.030). study-adverse MAE: 35.51/35.07, 50.74/48.76, 44.55/43.54,
41.77/39.46, 38.16/37.43 (1-6% higher at every cutoff). study-outcome is mixed. Both systematic gaps start in the
cutoff-1 learning session whose program later sessions retrain.

### Review point 4 (addition, registered before running): TeCoD's matcher on the lookup benchmark (`lookup-tecod/`)

TeCoD's released template selection (Qwen3-Embedding-4B search, Qwen3-Re4B NLI, `tools/relbench/tecod_server.py`) on
the same 96 requests. Pool: per definition one canonical question and 5 single-target phrasings sampled with seed 7 from
the catalog-generated training data MAVRA's judges use (156 examples); one SQL template per definition. A request
resolves to the matched template's definition, or none without an entailment match. Scored set-exact as in Table V.
Expected: two-definition requests always fail (TeCoD returns one template); reported as measured either way.

### Execution notes (replay)

- tpch, ssb, financial: commit 89322f2 (binary 43d3349f…), `results/maint-replay-20261111/{schema}-{main,nog9}` on noctis.
- tpcds, first attempt (89322f2) stopped by hand in `dupload` after 2,560 s (`tpcds-main-aborted-dupload`, not
  used): G9 computed the per-bucket series of every dedup revision, which needs `select distinct *` over the whole
  store_sales table (7+ minutes per definition, about 45 definitions). Commit 65f13fe skips that computation for
  dedup-only repairs with a proof (the previous revision held grain uniqueness on the learning snapshot, so unchanged
  buckets hold no exact duplicates and deduplication cannot change them) and logs `history_implied`. On tpch/ssb/
  financial the full computation ran and admitted every dedup repair, as the proof says. tpcds-main reran with
  65f13fe (binary 22b4874a…); tpcds-nog9 ran with 89322f2 (G9 off, so the change does not apply).
- Table VI's other policies on the eleven archived changes come from the same run (they are rerun, not archived),
  so all four rows use one binary per schema.
