# Fig. 5: shared validation as the number of agents grows (no model calls)

Question: after one data update, how much validation work do N agents cause when each
keeps its own validated memory, when definitions are shared but rechecked as a whole,
and with MAVRA's shared condition evidence?

Design (`postgres_shared_validation_scaling` in `src/integration_tests.rs`):

- 16 published metric definitions on four fact/date table pairs (sharing factor 4),
  200,000 rows per fact table, measures are unit conversions of the same net-paid sum.
- Update: an incremental load appends about 1% new business keys to every fact table;
  date tables are not written (the common case of a fact load). Every cell starts from
  the same data: rows appended by the previous cell are deleted first, and the DML and
  the statistics flush run in one statement batch so no counter arrives during measurement.
- After the update, N = 1, 2, 4, 8, 16, 32 agents each use all 16 definitions once,
  either one after another (staggered) or all at once (simultaneous).
- Policies:
  - per-agent: each agent has its own middle-layer instance with MAVRA's mechanism
    (private definitions and condition evidence), i.e. single-agent memory that validates;
  - full-recheck: one shared instance; a definition whose tables changed reruns all of its
    conditions on first use;
  - mavra: one shared instance; only conditions that read a changed table are rerun, and
    a condition's result at the current table versions is shared across definitions and agents.
  All three merge concurrent identical checks (single flight).
- Three randomized blocks (108 cells). Reported: maintenance check queries and database
  time of the use phase, median over blocks with the observed range.

Run on noctis (results in `results/shared-validation-<stamp>/`):

```
AGENTDB_TEST_URL=... cargo test --release postgres_shared_validation_scaling -- --ignored --nocapture
python3 exp/2026-11-01-shared-validation/analyse.py results/shared-validation-<stamp>
```

`analyse.py` writes `stats.json` here and `overleaf/gen/shared-validation.tex`;
`tools/figures/shared_validation.py` draws the figure and checks the printed values.

A query cache keyed by normalized check SQL and table versions reaches the same reuse as
MAVRA on these definitions (measured in `exp/2026-10-29-mechanism-pilot`, factor 1–8),
because MAVRA compiles one canonical query per condition; the comparison here is against
the approaches the paper argues about: validation repeated per agent and per definition.

## Results (2026-11-01, `results/shared-validation-1793471974128556`, archived in `cells.tgz`)

108 cells, every use served a valid definition. After the load, MAVRA runs 8 checks for
1–32 agents (3.9–5.0 s of database time). Per-agent validation runs 8 checks per agent
(256 at 32 agents; 126 s staggered, 132 s simultaneous: 25x and 32x MAVRA). Full recheck
runs 32 checks regardless of agents (16.6 s at 32 agents, 3.3x) and falls to 14 checks
(6.9 s, 1.7x) with simultaneous arrivals, where its in-flight merging combines identical
checks. Block ranges are within a few percent. The noctis LLM study was running during
the first half of the cells; medians over three randomized blocks are reported.
