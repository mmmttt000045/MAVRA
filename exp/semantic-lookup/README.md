# Semantic Lookup Scaling (26 to 1,000 Definitions) and Selective Risk–Coverage

**Paper Reference:** §4.3 (*Semantic Lookup Over Business Choices*) and §6.3 (*Q2: Semantic Lookup Accuracy, Latency, and Scaling*), Table 3 and Figure 8.

## Overview

This directory contains the nested enterprise metric catalogs, multi-style query sets, catalog-synthesized training corpora, GPU/LLM evaluation pipelines, and aggregated results for semantic definition lookup across **$M \in \{26, 100, 500, 1000\}$ definitions** spanning **8 enterprise analytical domains** (Retail Categories, Digital Retail Channels, B2B/SaaS, Supply Chain/WMS, Finance/Payments, CRM/Loyalty, AdTech Attribution, and Store/Service Operations).

### Evaluation Sets

- **390 Main Requests**:
  - [requests_orig_96.json](requests_orig_96.json) — 96 human-authored core requests (canonical names, synonyms, facet-specific, underspecified homonyms, and out-of-catalog absent metrics).
  - [requests_glm_174.json](requests_glm_174.json) — 174 human-audited cross-generator paraphrases (`GLM-4.5-Air`) of the core requests.
  - [requests_scale_120.json](requests_scale_120.json) — 120 multi-domain requests across $M \in \{100, 500, 1000\}$ (48 single-target, 48 homonymous 2-definition, 24 absent even at $M=1000$).
- **204 Held-Out Paraphrases**:
  - [requests_glm_scale.json](requests_glm_scale.json) — 204 audited cross-generator paraphrases of `requests_scale_120.json`.

### Compared Methods

1. `Name match` — Longest canonical metric-name substring match.
2. `Embedding top-1` — Off-the-shelf `BAAI/bge-m3` cosine top-1 (fixed and oracle thresholds + selective risk–coverage sweep).
3. `TeCoD` — Released `Qwen/Qwen3-Embedding-4B` + `Qwen3-Re4B-SQL-TeCoD-TMM` NLI template matcher over 6 examples per definition (`pool_1000.json`, 6,000 examples).
4. `Single CE (no diff)` — Three-seed 12-layer `XLM-RoBERTa` cross-encoder initialized from `BAAI/bge-reranker-base` trained on the exact same corpus without structured facets or peer differences.
5. `Top-8 + LLM` — Catalog-tuned `BAAI/bge-m3` top-8 candidates judged online by `deepseek-flash`.
6. `MAVRA (0-retrain)` — Frozen 26-definition peer-difference cross-encoder ensemble with absence widening (`W`), peer-group coherence (`C`), and agent confirmation on uncertain (`refer` / `similar`) replies.
7. `MAVRA (refreshed)` — Catalog-tuned `BAAI/bge-m3` top-8 + three 12-layer `XLM-RoBERTa` consistency judges (`BAAI/bge-reranker-base`, seeds 13/14/15) rendered with bounded peer differences + `W` + `C` + agent confirmation, plus matched-density training ablation.

## Curated Files

- [catalog_26.json](catalog_26.json), [catalog_100.json](catalog_100.json), [catalog_500.json](catalog_500.json), [catalog_1000.json](catalog_1000.json) — Strictly nested metric catalogs (`catalog_1000_sha256`: `f85bc3e9bc1da3c8c1e31593d6adc94c667bf5aa2ad15df3267adfffb5cd0ec2` in [benchmark-manifest.json](benchmark-manifest.json)).
- [pool_26.json](pool_26.json), [pool_1000.json](pool_1000.json) — Per-definition example pools (6 examples per definition).
- [train_26_clean.jsonl](train_26_clean.jsonl), [train_scale_extra.jsonl](train_scale_extra.jsonl), [train_scale_llm.jsonl](train_scale_llm.jsonl) — Catalog-synthesized training phrasings strictly disjoint from all 594 evaluation requests.
- [scale-summary.json](scale-summary.json), [risk-coverage.json](risk-coverage.json) — Aggregated accuracy, latency, token, paired McNemar test, and selective risk–coverage summaries consumed by `tools/figures/lookup_scale.py`.
- [analyse.py](analyse.py), [score_cache.py](score_cache.py), [policy.py](policy.py), [run_gpu.sh](run_gpu.sh), [run_ablation_gpu.sh](run_ablation_gpu.sh), [run_llm_methods.py](run_llm_methods.py), [run_gpu_methods.py](run_gpu_methods.py), [replay_plain_rule.py](replay_plain_rule.py) — End-to-end training, scoring, routing-policy replay, and LaTeX macro scripts.

## Reproduction

### 1. Generate Paper Macros & Figure 8 Offline (CPU Only, < 5 s)

```bash
python3 exp/semantic-lookup/analyse.py --tex results/gen/lookup-scale.tex
python3 tools/figures/build.py lookup-scale
```

### 2. Full GPU Training, Score Caching & Online Confirmation Pipeline

Install Python dependencies (`pip install -r exp/semantic-lookup/requirements.txt`), then run:

```bash
cd exp/semantic-lookup

# Deterministic 26-definition seed pairs + nested 1,000-definition catalogs
python3 build_seed_pairs.py
python3 build_scale_catalog.py

# Train catalog-tuned bge-m3 retriever + 3 peer-difference XLM-R judges and build score caches
bash run_gpu.sh

# Optional: run no-peer-difference and matched-density ablations
bash run_ablation_gpu.sh

# Replay routing policies and run online LLM confirmation / Top-8 + LLM judge
python3 policy.py --cache results/lookup/cache.json --out results/lookup
DEEPSEEK_API_KEY=... python3 run_llm_methods.py --for-llm results/lookup/for_llm --out results/lookup/llm

# Aggregate live outputs into summary JSONs and LaTeX macros
python3 analyse.py --results-dir results --tex ../../results/gen/lookup-scale.tex
```
