# Development Guide

## Prerequisites

- **Rust**: stable toolchain (`rustfmt`, `clippy`)
- **PostgreSQL**: PostgreSQL 16+ (local socket or TCP; CI uses `postgres:16`)
- **Python 3.10+**: standard library for `experiment-index.py` and `sync-paper-repo.py`; `numpy`, `pandas`, `lightgbm`, `scikit-learn`, `psycopg` for `tools/relbench/`; `matplotlib` for `tools/figures/`
- **LaTeX**: TeX Live (`latexmk` + `pdfLaTeX`) or Tectonic for `overleaf/build.sh`

## Common Workflows

```bash
# 1. Format, unit test, and lint Rust + check experiment index
make check

# 2. Run PostgreSQL integration tests against a test database
AGENTDB_TEST_URL=postgres://postgres:postgres@127.0.0.1:5432/postgres \
  cargo test --locked postgres_http_mock_lifecycle -- --ignored --nocapture
AGENTDB_TEST_URL=postgres://postgres:postgres@127.0.0.1:5432/postgres \
  RUST_MIN_STACK=16777216 \
  cargo test --locked postgres_scoped_sql_admission -- --ignored --nocapture

# 3. Run offline RelBench harness unit tests
make py-test

# 4. Build figures and compile the PVLDB manuscript
make figures
make paper
```
