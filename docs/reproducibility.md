# Artifact Reproducibility Guide

This guide maps every empirical claim, research question (Q1–Q5), table (Tables 1–6), and figure (Figures 1–9) in *MAVRA: Sharing and Maintaining Executable Knowledge for Data Agents* to its runnable code, datasets, external baselines, and benchmark summaries under [`exp/`](../exp/README.md).

---

## 1. Execution Tiers

MAVRA's evaluation separates **deterministic database/system benchmarks** (which require zero LLM API keys) from **live LLM agent experiments** and **GPU neural lookup training**:

1. **Tier A — Zero-API-Key Offline & Figure Verification (~2 minutes, CPU only)**:
   - Runs all 64 offline Rust unit tests, Python RelBench and mechanism unit tests, experiment index verification, and regenerates figures/macros from `exp/` benchmark summaries into `results/figures/` and `results/gen/`.
2. **Tier B — Deterministic PostgreSQL System & Replay Benchmarks (Zero API Keys, PostgreSQL 16+)**:
   - Runs isolated correctness regressions (`make db-test`), controlled maintenance policy sweeps (`maint-bench`), 4-schema × 12-update policy replay (`replay-bench`, **Table 6**), unseen parameter-binding checks (`binding-bench`, **Q5 C1**), and self-contained Q5 concurrency/scalability benchmarks (`q5_bench_tests`, **Figure 9** & **Q5**).
3. **Tier C — Neural Semantic Lookup & GPU Baselines (PyTorch, CPU or CUDA GPU)**:
   - Runs the `BAAI/bge-m3` + 3-model `XLM-RoBERTa` (`BAAI/bge-reranker-base`) lookup service ([`tools/lookup/`](../tools/lookup/README.md)) and reproduces the 26-to-1,000 definition scaling curves (**Table 3**, **Figure 8**).
4. **Tier D — Live LLM Multi-Agent & RelBench Exploration (`DEEPSEEK_API_KEY` / `OPENAI_API_KEY` / `ZHIPU_API_KEY`)**:
   - Runs live multi-agent exploration for workload characterization (**Table 1**), 16-agent TPC-DS sharing (**Q1 / Figure 6**), 11-update end-to-end evaluation (**Q3 / Figure 7 & Table 4**), and 5-cutoff RelBench feature reuse (**Q4 / Table 5**).

---

## 2. Environment & External Baseline Setup

### 2.1 Core Build & Python Dependencies

```bash
# Build release binary (./target/release/mavra)
cargo build --release --locked

# Core analysis, DuckDB TPC-H generator, and figure generation packages
python3 -m pip install -r tools/requirements.txt -r tools/figures/requirements.txt

# Offline RelBench harness test packages (or full tools/relbench/requirements.txt for live Q4 runs)
python3 -m pip install -r tools/relbench/requirements-test.txt
```

Copy [`.env.example`](../.env.example) to `.env` and set `MAVRA_DB_URL` (and `MAVRA_TEST_DB_URL` for isolated PostgreSQL test suites). See [`data/README.md`](../data/README.md) for dataset generation and loading commands.

### 2.2 External Memory & Lookup Baselines (`ACE`, `AWM`, `G-Memory`, `TeCoD`, `FeatPilot*`)

- **ACE** and **AWM** are vendored unmodified under [`third_party/ace/`](../third_party/ace/README.md) and [`third_party/awm/`](../third_party/awm/README.md) (Apache-2.0) and work out of the box.
- **FeatPilot\*** (no-LLM relational join search baseline for Q4) is implemented in [`tools/relbench/featpilot.py`](../tools/relbench/featpilot.py).
- **G-Memory** (used in Q3 and Q4): clone the upstream repository at pinned commit `7b581c5` into an isolated Python 3.12 virtual environment:
  ```bash
  mkdir -p results/ext
  git clone https://github.com/bingreeky/GMemory.git results/ext/GMemory
  git -C results/ext/GMemory checkout 7b581c5
  python3.12 -m venv results/ext/venv-gmem
  results/ext/venv-gmem/bin/pip install -r tools/relbench/requirements.txt
  ```
- **TeCoD** (used in Q2, Q3, and Q4): clone the upstream repository at pinned commit `6739e32` and download its two 4B HuggingFace checkpoints (`Qwen/Qwen3-Embedding-4B` and `smitxxiv/Qwen3-Re4B-SQL-TeCoD-TMM`):
  ```bash
  mkdir -p results/ext/tecod-models
  git clone https://github.com/SSLab-CSE-IITB/tecod.git results/ext/tecod-src
  git -C results/ext/tecod-src checkout 6739e32
  python3.12 -m venv results/ext/venv-tecod
  results/ext/venv-tecod/bin/pip install torch transformers sentence-transformers huggingface_hub
  results/ext/venv-tecod/bin/huggingface-cli download Qwen/Qwen3-Embedding-4B \
    --local-dir results/ext/tecod-models/Qwen3-Embedding-4B
  results/ext/venv-tecod/bin/huggingface-cli download smitxxiv/Qwen3-Re4B-SQL-TeCoD-TMM \
    --local-dir results/ext/tecod-models/Qwen3-Re4B-SQL-TeCoD-TMM
  ```

---

## 3. Question-by-Question Reproduction Commands

### Workload Motivation — Application SQL vs. Memoryless Agents (Section 1, Table 1)
- **Benchmark suite**: [`exp/workload-characterization/`](../exp/workload-characterization/README.md)
- **Regenerate Table 1 statistics from benchmark summaries**:
  ```bash
  python3 tools/workload-stats.py
  ```
- **Run live memoryless agent sessions (`workload-bench`)**:
  ```bash
  ./target/release/mavra --db "$MAVRA_DB_URL" workload-bench --agent deepseek --concurrency 3 --rounds 2
  ```

---

### Q1 — Cross-Agent Analytical Sharing & Data Restatement (Section 6.2, Figure 6)
- **Benchmark suite**: [`exp/population-sharing/`](../exp/population-sharing/README.md)
- **Regenerate Q1 summary macros and Figure 6**:
  ```bash
  python3 tools/population-stats.py --out results/gen
  make figures
  ```
- **Run live 16-agent sequential TPC-DS SF1 sharing (`No memory`, `Single-agent memory`, `Example retrieval`, `MAVRA`)**:
  ```bash
  # Requires tpcds_sf1 loaded via tools/tpcds-load.sh (see data/README.md)
  ./target/release/mavra --db "$MAVRA_DB_URL" metric-bench \
    --population --pop-agents 16 --pop-questions 7 \
    --agent deepseek --extractor deepseek \
    --modes direct,metric-private,metric-global-exref,metric-global-full
  ```

---

### Q2 — Lightweight Adaptive Semantic Resolution up to 1,000 Definitions (Section 6.3, Table 3 & Figure 8)
- **Benchmark suite**: [`exp/semantic-lookup/`](../exp/semantic-lookup/README.md) and [`exp/maintenance-guards/`](../exp/maintenance-guards/README.md)
- **Architecture note**: The three 12-layer `XLM-RoBERTa` peer-difference cross-encoders are fine-tuned from `BAAI/bge-reranker-base` (which uses the 12-layer `XLM-RoBERTa` encoder architecture) with seeds `13`, `14`, and `15`, paired with `BAAI/bge-m3` dense candidate recall.
- **Run the standalone semantic lookup HTTP service and attach `mavra serve`**:
  ```bash
  python3 -m pip install -r tools/lookup/requirements.txt
  python3 tools/lookup/service.py --catalog exp/semantic-lookup/catalog_1000.json --port 8090 &
  MAVRA_LOOKUP_URL=http://127.0.0.1:8090 ./target/release/mavra serve --mode full --no-etl
  ```
- **Reproduce catalog scaling (26 / 100 / 500 / 1,000 definitions across 8 domains) & risk–coverage curves**:
  ```bash
  python3 -m pip install -r exp/semantic-lookup/requirements.txt
  # Analyze lookup scaling summaries and regenerate Figure 8
  python3 exp/semantic-lookup/analyse.py
  python3 tools/figures/lookup_scale.py
  ```
  See [`exp/semantic-lookup/README.md`](../exp/semantic-lookup/README.md) for full GPU fine-tuning (`train_retriever.py`, `train_scale_ce.py`) and evaluation (`run_gpu.sh`, `run_gpu_methods.py`, `run_llm_methods.py`) commands.

---

### Q3 — Certified Repair under 11 Database Updates (Section 6.4, Figure 7 & Table 4)
- **Benchmark suite**: [`exp/schema-evolution/`](../exp/schema-evolution/README.md) and [`exp/maintenance-guards/`](../exp/maintenance-guards/README.md)
- **Regenerate Table 4 (compiled reuse vs. guided/unguided exploration) and Figure 7**:
  ```bash
  python3 exp/schema-evolution/analyse.py
  python3 exp/maintenance-guards/served-split.py
  make figures
  ```
- **Run live 11-update study across Synthetic Retail (1M) and TPC-H SF1**:
  ```bash
  python3 exp/schema-evolution/run-study.py --help
  ```

---

### Q4 — Cross-Cutoff Predictive Feature Reuse on RelBench (Section 6.5, Table 5)
- **Benchmark suite**: [`exp/relbench-predictive/`](../exp/relbench-predictive/README.md) and [`exp/relbench-attribution/`](../exp/relbench-attribution/README.md)
- **Regenerate Table 5 and predictive reuse statistics from benchmark summaries**:
  ```bash
  python3 tools/relbench/paper-stats.py --out results/gen
  python3 tools/relbench/frozen-summary.py
  ```
- **Run a 5-cutoff RelBench trajectory (`none`, `ace`, `awm`, `gmemory`, `tecod`, `featpilot`, `mavra-retry`)**:
  ```bash
  # Prepare rel-stack / rel-trial first (see data/README.md)
  python3 tools/relbench/harness.py \
    --arm mavra-retry --run 1 \
    --data results/relbench-data/rel-stack \
    --prep results/relbench-data/rel-stack-prep \
    --template relbench_stack_t1 \
    --out results/relbench-runs/mavra-rel-stack-r1
  ```

---

### Q5 — Design-Choice Ablations, Policy Replay & SF10 Scalability (Section 6.6, Table 6 & Figure 9)

All core Q5 database benchmarks are **100% deterministic and require zero LLM API keys**:

1. **C1 Extraction Gates & Unseen Parameter Bindings** ([`exp/premise-optimization/`](../exp/premise-optimization/README.md), [`exp/maintenance-guards/`](../exp/maintenance-guards/README.md), [`exp/tpcds-scaling/`](../exp/tpcds-scaling/README.md)):
   ```bash
   ./target/release/mavra --db "$MAVRA_DB_URL" binding-bench \
     --defs exp/population-sharing/tpcds-defs.json --rows 200000
   python3 tools/sharing-stats.py --out results/gen
   ```

2. **C3 4-Schema × 12-Update Policy Replay — Table 6** ([`exp/policy-replay/`](../exp/policy-replay/README.md), [`exp/cache-baseline-tpcds/`](../exp/cache-baseline-tpcds/README.md), [`exp/multi-schema-generality/`](../exp/multi-schema-generality/README.md)):
   ```bash
   # Synthetic retail replay across maintenance policies (condition, definition, schema, revoke, tabletest)
   ./target/release/mavra --db "$MAVRA_DB_URL" replay-bench \
     --libs exp/schema-evolution/bank-synthetic.json \
     --schema synthetic --rows 200000 \
     --policies condition,definition,schema,revoke,tabletest

   # TPC-DS SF1 / SF3 / SF10 scaling replay (requires tpcds_sf1 / tpcds_sf3 / tpcds_sf10 loaded)
   ./target/release/mavra --db "$MAVRA_DB_URL" replay-bench \
     --libs exp/population-sharing/tpcds-defs.json \
     --schema tpcds --tpcds-db tpcds_sf1 --sql-timeout-secs 1800
   ```

3. **Shared Validation Scaling (Figure 9), Snapshot-Bound TOCTOU Isolation, 16-Shard Sustained Writes & Repair Ambiguity** ([`src/q5_bench_tests.rs`](../src/q5_bench_tests.rs), [`exp/shared-validation/`](../exp/shared-validation/README.md), [`exp/mechanism-studies/`](../exp/mechanism-studies/README.md)):
   ```bash
   export MAVRA_TEST_DB_URL=postgres://postgres:postgres@127.0.0.1:5432/postgres

   # Run all self-contained Q5 PostgreSQL mechanism benchmarks
   cargo test --release --locked q5_bench_tests:: -- --ignored --nocapture --test-threads=1

   # Or run an individual Q5 benchmark (e.g., 1-to-32 agent shared validation scaling for Figure 9)
   cargo test --release --locked q5_bench_tests::postgres_shared_validation_scaling -- --ignored --nocapture --test-threads=1
   ```

---

## 4. Regenerating All Paper Figures Standalone

[`Makefile`](../Makefile) builds all vector figures (`results/figures/*.pdf`) and summary macros (`results/gen/*.tex`) directly from the benchmark summaries in `exp/` out-of-the-box using standard Matplotlib fonts (and automatically uses TeX Live `libertine`/`inconsolata` fonts when installed):

```bash
make figures
```
