# Development and Testing Guide

## 1. Prerequisites

- **Rust**: Stable toolchain (`1.75+`) with `rustfmt` and `clippy`.
- **PostgreSQL**: Version `16+` for database integration regressions and benchmarks (a role with `CREATEDB` privilege is sufficient; `SUPERUSER` is not required).
- **Python**: Version `3.10+` (`3.12` recommended for RelBench and neural lookup tools).

---

## 2. Fast Offline Checks (No Database, Network, or API Keys)

The default Rust unit test suite (`64` offline unit tests, with PostgreSQL integration and Q5 scalability tests gated behind `#[ignore]`), Clippy lints, Python RelBench and mechanism unit tests, and experiment catalog validator run completely offline using in-memory mocks and local loopback stubs:

```bash
# Formatting, offline Rust unit tests, Clippy (-D warnings), and experiment index check
make check

# Offline Python unit tests for the RelBench harness and mechanism analysis scripts
python3 -m pip install -r tools/relbench/requirements-test.txt
make py-test
```

Without `make` (including Windows PowerShell):

```powershell
cargo fmt --check
cargo test --locked
cargo clippy --locked --all-targets -- -D warnings
python tools/experiment-index.py --check
python -m unittest discover -s tools/relbench -p "test_*.py"
python -m unittest discover -s exp/mechanism-studies
```

---

## 3. Isolated PostgreSQL Regressions (`make db-test`)

Integration regressions in [`src/integration_tests.rs`](../src/integration_tests.rs) connect to `MAVRA_TEST_DB_URL` (or `AGENTDB_TEST_URL`), create a uniquely named temporary database per test from [`data/mock_fixture.sql`](../data/mock_fixture.sql), and drop it automatically on completion, failure, or panic.

Start a disposable PostgreSQL 16 container if you do not have a local instance:

```bash
docker run -d --name mavra-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16
```

Run the integration suite on Linux / macOS:

```bash
export MAVRA_TEST_DB_URL=postgres://postgres:postgres@127.0.0.1:5432/postgres
make db-test
```

Or on Windows PowerShell:

```powershell
$env:MAVRA_TEST_DB_URL = 'postgres://postgres:postgres@127.0.0.1:5432/postgres'
$env:RUST_MIN_STACK = '16777216'
cargo test --locked integration_tests:: -- --ignored --test-threads=1
```

The regression suite verifies:
- HTTP tool lifecycle, request context isolation, and single-flight check coalescing;
- Query-scoped SQL admission, join fan-out rejection (`BadPath`), and CTE grain uniqueness proofs;
- Point-in-time `LATERAL` feature fusion and future-row temporal leakage prevention;
- Date-key alias repair, equivalence optimization with premise invalidation, and certified single-edit repair (`G8`/`G9`);
- Concurrent `REPEATABLE READ` snapshot binding and 16-shard `mavra_versions` version tracking.

---

## 4. Self-Contained Scalability & Mechanism Benchmarks (`q5_bench_tests`)

Heavy row-count and multi-session PostgreSQL benchmarks live in [`src/q5_bench_tests.rs`](../src/q5_bench_tests.rs) (`#[ignore]` by default so CI stays fast):

```bash
export MAVRA_TEST_DB_URL=postgres://postgres:postgres@127.0.0.1:5432/postgres
cargo test --release --locked q5_bench_tests:: -- --ignored --nocapture --test-threads=1
```

Optional row-scale override for scenario regressions: set `MAVRA_SCENARIO_ROWS` (default `20000` / `200000` depending on test).

---

## 5. Codebase Conventions

- **Separation of runtime and evaluation**: Runtime profiles belong in [`src/middle/profiles.rs`](../src/middle/profiles.rs); production serving (`mavra serve`) must never depend on benchmark-only modules under `src/bench/`.
- **Formatting**: Rust code follows [`rustfmt.toml`](../rustfmt.toml) (`max_width = 140`, `use_small_heuristics = "Max"`). All compiler and Clippy warnings are treated as errors in CI.
- **Experiment catalog integrity**: Every directory under `exp/` is indexed by `exp/catalog.json` and validated in CI via `python3 tools/experiment-index.py --check`. Run `python3 tools/experiment-index.py` after updating `exp/catalog.json`.
