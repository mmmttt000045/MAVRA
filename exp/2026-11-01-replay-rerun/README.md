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
