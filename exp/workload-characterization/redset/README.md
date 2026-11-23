# Redset Production Warehouse Workload Baseline

Statistics computed from the public Amazon Redset dataset (van Renen et al.,
"Why TPC Is Not Enough: An Analysis of the Amazon Redshift Fleet", VLDB 2024;
<https://github.com/amazon-science/redset>, CC BY-NC 4.0) as a production
application/BI warehouse workload baseline for Table 1 of the MAVRA paper. All
metrics are archived in [redset_stats.json](redset_stats.json) alongside the
exact definition, numerator, and denominator of every statistic.

## Public Dataset Inputs (`s3://redshift-downloads/redset/`)

| Upstream Redset Parquet Path | Description |
|---|---|
| `provisioned/parts/N.parquet` (200 files, 17.66 GB) | One file per provisioned cluster (`instance_id = N`) |
| `serverless/full.parquet` (0.32 GB) | All 200 serverless clusters in a single Parquet file |
| `*/sample_0.01.parquet`, `*/sample_0.001.parquet` | Uniform random row samples (**not used** — subsampling breaks per-cluster temporal streams) |

All statistics in [redset_stats.json](redset_stats.json) are computed over the
**complete per-cluster streams of all 200 provisioned and all 200 serverless
clusters** (no cluster subsampling, no random seed). Time span: `2024-03-01` to
`2024-05-31` (three months). Provisioned and serverless variants are reported
separately.

Redset is a stratified sample of clusters selected to span observed busyness
levels rather than a uniform fleet average; the statistics serve as an empirical
reference for recurring production BI/application query streams.

## Upstream Column Semantics (from the Redset Specification)

- `instance_id`: Uniquely identifies a Redshift cluster.
- `user_id`: Identifies the database user that issued the query.
- `query_id`: Unique per cluster instance.
- `arrival_timestamp`: Timestamp when the query arrived on the system.
- `feature_fingerprint`: 64-hex hash of the query structure (proxy for template equivalence; upper-bounds text-template repetition).
- `was_aborted`: Whether the query was aborted during its lifetime.
- `was_cached`: Whether the query was answered from the result cache.
- `cache_source_query_id`: For result-cache hits, the `query_id` that populated the cache entry.
- `query_type`: Statement category (`select`, `copy`, `insert`, `other`, ...).
- `num_permanent_tables_accessed`, `num_external_tables_accessed`, `num_system_tables_accessed`: Table access counts by relation kind.

## Encoding Properties Verified on the Dataset

- **Result-cache hits are logged with `query_type = 'other'`.** Every `was_cached = 1` row has NULL `feature_fingerprint` and NULL table counts; `cache_source_query_id` resolves to an earlier row in the same cluster for 96.3% (provisioned) and 99.8% (serverless) of cached rows (the remainder predate the 3-month window), and resolved sources are `select` statements in 99.96% (provisioned) and 100% (serverless) of cases.
- `feature_fingerprint` is cluster-scoped and pure with respect to `query_type` and system-table access.
- `query_id` is not monotone in arrival time; stream order is `(arrival_timestamp, query_id)`.
- `was_aborted` rows exist across all query types without SQL error codes.

## Metric Definitions

- **Query classes**: `all` = every row; `read` = `query_type = 'select' OR was_cached = 1` (primary analytical read definition); `select` = `query_type = 'select'` (executed selects only). Each statistic is evaluated on that class's per-cluster chronological stream.
- **Effective fingerprint and table counts**: For `was_cached = 1` rows, resolved from the `cache_source_query_id` row in the same cluster.
- **Aggregation**: **Pooled** = $\sum \text{numerator} / \sum \text{denominator}$ across all clusters of the variant. **Cross-cluster** = per-cluster ratio summarized by `median [p25, p75]` across clusters with denominator $\ge 1{,}000$ ($k$ = eligible clusters).
- Machine-readable definitions and exact numerators/denominators are stored in [redset_stats.json](redset_stats.json).

## Dataset Context

| Metric | Provisioned | Serverless |
|---|---|---|
| Clusters | 200 (143 with $\ge 1{,}000$ queries; 111 with $\ge 1{,}000$ read queries) | 200 (39 with $\ge 1{,}000$ queries; 29 with $\ge 1{,}000$ read queries) |
| Queries (`all` / `read` / `select`) | 433,107,811 / 133,764,075 / 87,708,340 | 8,244,382 / 2,549,708 / 2,171,354 |
| Read share of all queries | 30.9% | 30.9% |
| Result-cache hits (`was_cached`) | 46,055,735 (1,718,428 with source before window) | 378,354 (871) |
| Principals `(cluster, user_id)` | 190,196 (187,003 in 3 ephemeral-ID clusters: 13, 52, 97) | 2,412 |
| Median queries / users per cluster | 31,045 / 2 | 33 / 1 |
| Window | `2024-02-29 23:59:55` .. `2024-05-31 00:00:04` | `2024-02-29 23:59:58` .. `2024-05-30 23:59:30` |

## Summary Results

Cell format: `pooled; cross-cluster median [p25, p75] k=#eligible clusters`.

| Statistic | Provisioned Read | Provisioned All | Serverless Read | Serverless All |
|---|---|---|---|---|
| `fp_repeat_frac` | 93.45%; 91.72% [82.66%, 96.58%] k=111 | 90.16%; 84.68% [74.40%, 94.15%] k=143 | 93.11%; 91.16% [73.55%, 95.32%] k=29 | 87.52%; 91.20% [78.86%, 97.11%] k=39 |
| `fp_repeat_frac_from_apr1` | 93.88%; 91.19% [82.74%, 96.64%] k=108 | 91.06%; 84.92% [76.15%, 95.04%] k=127 | 91.22%; 92.24% [72.64%, 95.70%] k=24 | 87.36%; 91.60% [77.38%, 98.60%] k=35 |
| `distinct_fp_per_100` | 6.6; 8.3 [3.4, 17.3] k=111 | 9.8; 15.3 [5.8, 25.6] k=143 | 6.9; 8.8 [4.7, 26.5] k=29 | 12.5; 8.8 [2.9, 21.1] k=39 |
| `distinct_fp_per_100q_block` | 37.2; 32.3 [19.1, 51.0] k=111 | 40.9; 43.5 [27.9, 56.3] k=143 | 29.1; 21.6 [9.4, 49.9] k=29 | 35.5; 33.4 [14.1, 45.0] k=39 |
| `top10_fp_share` | 32.41%; 33.46% [12.94%, 60.77%] k=111 | 33.72%; 37.38% [24.60%, 59.17%] k=143 | 51.27%; 35.63% [20.48%, 86.31%] k=29 | 53.41%; 45.53% [32.02%, 77.50%] k=39 |
| `cached_frac` | 34.43%; 13.30% [1.72%, 36.40%] k=111 | 10.63%; 1.14% [0.07%, 9.80%] k=143 | 14.84%; 8.72% [1.35%, 20.91%] k=29 | 4.59%; 1.20% [0.00%, 6.38%] k=39 |
| `aborted_frac` | 0.35%; 0.07% [0.00%, 0.49%] k=111 | 0.51%; 0.02% [0.00%, 0.22%] k=143 | 0.28%; 0.17% [0.00%, 1.06%] k=29 | 0.91%; 0.14% [0.00%, 0.50%] k=39 |
| `sys_table_frac` | 7.63%; 2.20% [0.07%, 22.75%] k=111 | 2.39%; 0.25% [0.00%, 2.79%] k=143 | 40.12%; 0.26% [0.03%, 2.50%] k=29 | 12.42%; 0.04% [0.00%, 0.97%] k=39 |
| `sys_only_frac` | 7.59%; 2.16% [0.06%, 22.75%] k=111 | 2.35%; 0.19% [0.00%, 2.57%] k=143 | 40.12%; 0.26% [0.03%, 2.50%] k=29 | 12.42%; 0.04% [0.00%, 0.97%] k=39 |
| `xuser_same_fp_60s` | 0.61%; 0.01% [0.00%, 0.23%] k=111 | 4.61%; 0.01% [0.00%, 1.80%] k=143 | 0.08%; 0.00% [0.00%, 0.01%] k=29 | 0.52%; 0.00% [0.00%, 0.01%] k=39 |
| `suser_same_fp_60s` | 72.39%; 63.81% [34.52%, 80.51%] k=111 | 69.68%; 64.58% [48.09%, 80.77%] k=143 | 67.15%; 62.97% [43.54%, 81.23%] k=29 | 66.49%; 64.85% [47.74%, 87.39%] k=39 |
| `fp_first_seen_other_user_frac` | 3.67%; 0.24% [0.00%, 2.64%] k=111 | 6.91%; 0.27% [0.00%, 5.34%] k=143 | 0.32%; 0.21% [0.00%, 1.82%] k=29 | 2.98%; 0.03% [0.00%, 5.59%] k=39 |

## Methodological Caveats

1. **Fingerprint vs. SQL template**: Redset's `feature_fingerprint` is a structural feature hash rather than a normalized SQL AST, so `fp_repeat_frac` upper-bounds exact template repetition, while `cached_frac` lower-bounds exact literal-query repetition.
2. **Left censoring**: Counting repetitions from `2024-04-01` onward (using March as warm-up history) shifts pooled repeat rates by at most 2.7 percentage points.
3. **`was_aborted` vs. SQL error rate**: Redset records mid-execution aborts/cancellations without parse/bind error codes, so `aborted_frac` is not directly comparable to interactive agent SQL syntax/schema error rates.
4. **Database principals vs. end users**: BI dashboards often multiplex many human users over shared service accounts, whereas three provisioned clusters (`13`, `52`, `97`) create short-lived principals; reporting both pooled and cross-cluster medians accounts for this skew.

## Curated File

- [redset_stats.json](redset_stats.json) — Complete machine-readable statistics, definitions, numerators, denominators, and cross-cluster quantiles for all 200 provisioned and 200 serverless clusters.
