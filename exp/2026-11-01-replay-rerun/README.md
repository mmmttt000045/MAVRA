# Fixed-library replay by maintenance policy (Table VI, no model calls)

The replay benchmark fixes learned definition libraries and varies only maintenance:
every change starts from the original data, each policy decides per definition whether
to serve it, and the served revision's canonical SQL is compared with the reference
answer. Outcomes per question instance: served correct, served wrong, or refused.

Libraries and data are the archived ones (TPC-DS SF1: `exp/2026-10-02-cache-baseline-tpcds`;
TPC-H SF1, SSB, BIRD financial: `exp/2026-10-11-generality`). Policies:

- revoke: invalidate a definition on every write to its tables;
- schema: keep a definition while its referenced columns are unchanged;
- tabletest: dbt-style table tests (grain and key uniqueness, non-null, referential
  integrity) rerun after every change, quarantining definitions on failing tables;
- condition: MAVRA, condition-level maintenance with restricted repair and a
  learning-snapshot regression reference.

2026-11-01 rerun: the condition policy was rerun with the current binary, which adds the
date-key repair (alternative `yyyymmdd`/day-number encodings over the date dimension).
The other policies share no code with the repair and keep their archived outcomes. The
table counts instances present for all four policies. Commands (noctis, `results/replay-rerun-20261101/run.sh`):

```
agentdb-mid --pool 8 --out <dir>/<s> replay-bench --spec exp/2026-10-11-generality/schemas/<s>.json \
  --libs exp/2026-10-11-generality/libs/<s>-kept.json --policies condition --oracles snapshot --sql-timeout-secs 1800
agentdb-mid --pool 8 --out <dir>/tpcds replay-bench --schema tpcds --libs results/tpcds-library.json \
  --policies condition --oracles snapshot --sql-timeout-secs 1800
python3 exp/2026-11-01-replay-rerun/analyse.py <dir>
```

`analyse.py` writes `replay-policies.json` (table, per-change counts, and every MAVRA
outcome that differs from the archived run) and `overleaf/gen/replay-policies.tex`.

## Result (2026-11-01, binary 67e2fc83 at 96da0bc; reports in `rerun-reports.tgz`)

1,641 common instances. MAVRA: non-breaking 534/0/0, covered breaks 600/3/237, not covered
89/115/63 (correct/wrong/refused). Compared with the archived condition-policy run, the
only differences are latekey instances on TPC-DS (135) and SSB (33) moving from refused to
correct through the date-key repair; TPC-H and BIRD financial store late batches with NULL
dates, which no encoding can repair, and are unchanged. Other policies (archived):
invalidate on every write 0/0/534, 0/0/840, 0/0/267; schema check 534/0/0, 204/636/0,
110/157/0; table tests 534/0/0, 0/0/840, 89/115/63. The SSB and TPC-DS runs spent most of
their time in repeated failed or ambiguous grain-repair searches (one per definition on
6–12M-row facts); caching failed searches per table version would remove that cost.

## Final binary (2026-11-01 afternoon, used in the paper; `results/replay-final2-20261101`, `rerun-final-reports.tgz`)

Rerun of the condition policy with the final binary (HEAD d648f3d): exact-duplicate repair, the
prescreened and shared grain-repair search, and deduplicated facts filtered by the period's date
keys before DISTINCT. Wall time: financial 81 s, TPC-H 991 s, SSB 1,069 s, TPC-DS 4,878 s (four
schemas in parallel). MAVRA: non-breaking 534/0/0, covered breaks 804/3/33 (96% correct), not
covered 89/115/63. Against the archived condition-policy run, duplicate-load instances move from
refused to correct on all four schemas (TPC-DS 135, SSB 33, TPC-H 27, financial 9) through the
exact-duplicate repair, and late-key instances on TPC-DS (135) and SSB (33) through the date-key
repair (`replay-policies.json`, audit). The 3 wrong answers
remain the TPC-H Q12 definition with a null auxiliary filter. Other policies keep their archived
outcomes: schema check 534/0/0, 204/636/0, 110/157/0; table tests 534/0/0, 0/0/840, 89/115/63;
invalidate on every write refuses everything. An intermediate rerun with the binary before the
DISTINCT pushdown (`results/replay-final-20261101`) was stopped in the TPC-DS duplicate-load phase,
where each query deduplicated the whole store_sales table; it is not used.
