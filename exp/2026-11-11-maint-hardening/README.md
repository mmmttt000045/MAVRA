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

### Review point 6 (addition, registered before running): sustained reads and writes (`postgres_sustained_writes`, 66c2181)

16 shared definitions on 4 fact/date pairs (200k rows per fact, as in Fig. 10). 64 sessions (8 agents x 8 rounds) each
use all 16 definitions, one after another. After each session, lambda appends of about 200 new-key rows (0.1%) go to the
fact tables in turn; lambda in {0, 1/8, 1/2, 2}. Policies: MAVRA (condition level, shared results) and full recheck
(definition level, no sharing), same derived conditions. Reported: condition checks executed / reused / skipped, database
time of the use phase per use, and the version trigger's write overhead (the same 200-row insert with and without the
statement-level trigger, 60 times each, interleaved). One run; latencies were measured while the change-study cells,
the TPC-DS replay and the TeCoD matcher shared the machine, so check counts are the primary result.

### Review point 4 (addition, registered before running): cross-generator paraphrases (`lookup-glm/`)

GLM (glm-5.3, Zhipu API), a model family that wrote none of the training phrasings, rewrites each of the 96 test
requests twice without adding or removing a metric choice (agent style with business context; colloquial or English).
Gold sets are those of the originals (same stated choices). Rewrites equal to a training phrasing are dropped. The three
MAVRA judges (unchanged, no retraining) run end to end with the same thresholds (`serve.py`, first ask). Reported:
first-response set-exact, direct rate and precision, references containing the gold set. This tests unseen wording from
another generator on the same catalog; it is not a human-written or second-schema test.

Results (2026-11-11). GLM wrote 182 rewrites; reading each against its original, 8 that add or drop a metric choice
were removed (`audit.json`), leaving 174 (gold: 108 single, 32 two-definition, 34 absent). Same judges, thresholds, and
code as Table V.

| Method (174 GLM rewrites) | Exact | Final | Absent rejected | Notes |
|---|---:|---:|---:|---|
| Name match | 19.5% | 19.5% | 34/34 | |
| Embedding top-1 (oracle threshold) | 45.4% | 45.4% | 11/34 | |
| Full-catalog LLM judge (deepseek-flash) | 95.4% | 95.4% | 32/34 | 2.57 s, 1.6k tokens |
| MAVRA first response | 81.0% (141) | 87.9% (153) after confirmation | 29/34 | direct 64.4% at 91.1% precision; 0.10 s lookup |

On the authors' 96 requests the same pipeline reached 92% / 99%. The judges were trained only on DeepSeek phrasings;
another generator's wording costs about 11 points after confirmation, mostly on absent metrics (26/34 first response)
and choice descriptions (23/32). The LLM judge loses 4 points. Per the stopping rule this is reported as is; training on
phrasings from several generators is the next method step, to be tested on a third generator.

TeCoD matcher results (`lookup-tecod/tecod-summary.json`): exact 25/96 (26%); entailment match on 13 requests only;
single-target 8/61, two-definition 0/18 (one template per answer), absent 17/17 rejected. 59.6 s per lookup on the
shared CPU (two 4B models in float32, contended by the change-study cells), so its time is not comparable.

## Results: replay (A + B + C), four schemas, twelve classes (`replay-hardening.json`, Table VI)

| Policy | Non-breaking (534) | Covered breaks (840) | Premise changes (432) |
|---|---|---|---|
| Invalidate on every write | 0/0/534 | 0/0/840 | 0/0/432 |
| Schema check only | 534/0/0 | 204/636/0 | 173/259/0 |
| dbt-style table tests | 534/0/0 | 0/0/840 | 89/115/228 |
| MAVRA (A+B+C) | 534/0/0 | 804/0/36 | 201/0/231 |

- MAVRA serves 0 wrong answers in 1,806 instances. On the eleven archived changes the 11-01 binary served 118 wrong
  (3 tpch/latekey q12, 115 unit); A turns the 3 into withholdings, C turns 104 served-wrong unit instances into
  withholdings and also withholds 40 unit instances that were correct (ratio measures are scale-invariant).
- B: 223 checked repairs passed (dimhist, dupload on tpch/ssb/financial, latekey, revision, status, reclass where the
  attribute is unread), 45 TPC-DS dedup repairs passed by the proof, 0 false rejections. Reclass: 3 repairs moved
  history (tpch q17: 1,529 of 2,258 buckets; ssb: 2 definitions) and were withheld (9 instances). Without G9 those 9 are
  served under current attribution and wrong (e.g. tpch q17 1,573,577 vs as-of 3,006,724). TPC-DS definitions that join
  item never read i_category, so reclass is correct with and without G9 (135/135).
- Predictions in the design: all met, except that C also withholds 40 correct ratio instances (now stated in the paper).

## Results: D, closest simple baseline (`results/change-study-20261111`, 12 cells, CNY 7.03, 2,847 calls, 0 errors)

Both schemas, three runs (same banks, prompts, model, feedback as the 11-01 study; published-memory arms archived).

| Group | MAVRA (new binary) | Shared recheck | best published memory |
|---|---|---|---|
| Held-out | 100.0 · 12.8k · 5 s | 100.0 · 13.8k · 5 s | 100.0 (ACE, TeCoD) |
| Non-breaking | 100.0 · 13.2k · 8 s | 100.0 · 14.5k · 16 s | 98.8 (TeCoD) |
| Covered breaks | 88.6 (0.9 wrong) · 15.7k · 17 s | 74.6 (6.1 wrong, 19.3 clarify) · 34.6k · 38 s | 69.3 (TeCoD) |
| Premise changes | 85.7 · 65.2k · 45 s | 81.0 · 49.1k · 45 s | 71.4 (ACE) |
| All | 93.1 · 22.1k · 17 s | 86.6 · 28.0k · 28 s | 80.4 (ACE) |

- All 210 MAVRA answers served from a definition (declared valid revision) were correct; its 5 wrong answers came from
  agents' own SQL: 1 latekey question in a run where M1 was never learned (both learning questions ended in
  clarification), 4 backup-copy questions answered after the definition was withheld (23.81 vs 23.80; 0.00 vs -0.01).
- Shared recheck could use a definition on 14 of 114 covered-break answers; the rest re-explored (71 correct, 22
  clarification, 7 wrong).
- Unit: MAVRA 28/30 correct (11-01 binary: 0/30). The scale condition withholds the definition; agents read the reason
  and convert cents back (trace: synthetic-r1 M1-P1). This is the agent's inference, not a MAVRA decision.
- Earlier MAVRA numbers (11-01 binary) stay in `exp/2026-11-01-change-study/README.md`.
- Not rerun with the new binary: the TPC-DS sharing/restatement study (Fig. 8) and RelBench (Table III); their
  mechanisms touched by A-C are the restatement repair (G9 would compare unchanged months) and feature maintenance
  (features are revoked on failure, no repair).
