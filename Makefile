.DEFAULT_GOAL := help
PYTHON ?= python3

.PHONY: help check index index-check py-test db-test q5-bench figures

help:
	@printf '%s\n' \
	  'check         Experiment index check, Rust format, unit tests, and Clippy' \
	  'index         Regenerate exp/README.md from exp/catalog.json' \
	  'index-check   Validate exp/catalog.json coverage and file references' \
	  'py-test       Run offline Python unit tests (tools/relbench and exp/mechanism-studies)' \
	  'db-test       Run PostgreSQL regressions (requires MAVRA_TEST_DB_URL)' \
	  'q5-bench      Run self-contained Q5 PostgreSQL mechanism benchmarks' \
	  'figures       Regenerate all paper vector figures in results/figures/'

check: index-check
	cargo fmt --check
	cargo test --locked
	cargo clippy --locked --all-targets -- -D warnings

index:
	$(PYTHON) tools/experiment-index.py

index-check:
	$(PYTHON) tools/experiment-index.py --check

py-test:
	$(PYTHON) -m unittest discover -s tools/relbench -p "test_*.py"
	$(PYTHON) -m unittest discover -s exp/mechanism-studies

db-test:
	RUST_MIN_STACK=16777216 cargo test --locked integration_tests:: -- --ignored --test-threads=1

q5-bench:
	RUST_MIN_STACK=16777216 cargo test --release --locked q5_bench_tests:: -- --ignored --nocapture --test-threads=1

figures:
	$(PYTHON) tools/figures/mechanism.py
	$(PYTHON) tools/figures/build.py
