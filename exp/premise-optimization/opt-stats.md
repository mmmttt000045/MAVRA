cell: r1-metric-global-opt-named, 3519 s; optimizations = 9

Optimization pass: 9 definitions evaluated, 9 published as r1, 474 s

| Definition | Outcome | Candidate Rewrite | Source | Exec ms (r0 -> r1) | Saving | 95% CI ms | Periods | Shared Buffers (r0 -> r1) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| metric:electronics_store_revenue | published r1 | rewrite period predicate to date_sk range without joining date_dim | rule | 29.4 -> 24.8 | 15.6% | [-7.6, -1.5] | 14 | 95090 -> 87128 |
| metric:electronics_store_revenue#2 | published r1 | rewrite period predicate to date_sk range without joining date_dim | rule | 29.9 -> 24.9 | 16.6% | [-8.1, -1.8] | 14 | 95470 -> 87324 |
| metric:catalog_revenue | published r1 | rewrite period predicate to date_sk range without joining date_dim | rule | 14.8 -> 12.1 | 18.4% | [-4.7, -0.8] | 14 | 61530 -> 53886 |
| metric:store_revenue | published r1 | rewrite period predicate to date_sk range without joining date_dim | rule | 29.1 -> 23.3 | 19.8% | [-9.1, -2.5] | 14 | 95000 -> 87038 |
| metric:store_revenue#2 | published r1 | rewrite period predicate to date_sk range without joining date_dim | rule | 28.6 -> 23.2 | 18.7% | [-8.6, -2.1] | 14 | 95380 -> 87234 |
| metric:store_return_rate | published r1 | rewrite period predicate to date_sk range without joining date_dim | rule | 173.1 -> 110.5 | 36.1% | [-74.4, -50.6] | 14 | 1458917 -> 1668787 |
| metric:store_return_rate#2 | published r1 | rewrite period predicate to date_sk range without joining date_dim | rule | 172.6 -> 112.2 | 35.0% | [-69.0, -51.8] | 14 | 1462147 -> 1675324 |
| metric:store_return_amount | published r1 | rewrite period predicate to date_sk range without joining date_dim | rule | 14.6 -> 10.7 | 26.7% | [-5.7, -2.1] | 14 | 95281 -> 49791 |
| metric:store_return_amount#2 | published r1 | rewrite period predicate to date_sk range without joining date_dim | rule | 13.8 -> 9.8 | 29.4% | [-6.6, -1.6] | 14 | 90238 -> 48882 |

Rejected LLM candidates:
  model proposal: 1 candidate, 1 call, 51 s, errors []
  model proposal: 1 candidate, 1 call, 60 s, errors []
  model proposal: 1 candidate, 1 call, 67 s, errors []
  model proposal: 1 candidate, 1 call, 41 s, errors []
  model proposal: 1 candidate, 1 call, 42 s, errors []
  model proposal: 1 candidate, 1 call, 52 s, errors []
  model proposal: 1 candidate, 1 call, 75 s, errors []
  model proposal: 1 candidate, 1 call, 27 s, errors []
  model proposal: 1 candidate, 1 call, 35 s, errors []

| Phase | Optimized (`-opt`) Correct / N | Control (`-snap`) |
| --- | --- | --- |
| holdout | 15/15 | 15/15 |
| append | 9/9 | 9/9 |
| backfill | 6/6 | 6/6 |
| correct | 9/9 | 9/9 |
| addcol | 6/6 | 6/6 |
| status | 6/6 | 6/6 |
| revision | 9/9 | 8/9 |
| dupload | 5/9 | 6/9 |
| dimhist | 3/3 | 3/3 |
| latekey | 1/9 | 2/9 |
| unit | 4/9 | 4/9 |
| mirror | 5/6 | 3/6 |
| all | 78/96 (81%) | 77/96 (80%) |

Holdout consumer-agent SQL: 15 questions, 9 adopted date_sk range predicate, 13 joined date_dim
  EXPLAIN execution time: mean 122.1 ms, median 76.7 ms
  Control (`-snap`): mean 100.3 ms, median 58.4 ms
