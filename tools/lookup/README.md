# MAVRA Neural Semantic Lookup Service (`tools/lookup/`)

This module provides the HTTP semantic definition resolver (`POST /resolve`, `GET /health`) implementing Section 4.3 of the MAVRA paper and wired into the Rust middleware via `MAVRA_LOOKUP_URL`:

1. **Stage-1 Dense Recall (`BAAI/bge-m3`)**: Encodes published metric definitions (cached by SHA-256 content hash) and retrieves top-$K=8$ candidates (widened to $K_{\max}=32$ for out-of-catalog absence verification).
2. **Stage-2 Peer-Difference Consistency Judging (`BAAI/bge-reranker-base`, 12-layer `XLM-RoBERTa`)**: Renders each candidate alongside its structured business-attribute projection $B(I) = (F, e, \mathrm{AGG}_e, \tau, \varphi)$ and bounded facet differences against up to 4 closest homonymous or same-domain peers in the active catalog, averaging sigmoid scores across the 3-seed cross-encoder ensemble.
3. **Stage-3 Selective Routing (`(0.10, 0.90)` Abstention Band)**: Routes requests into `Hit`, `Diffs`, `Refer`, or `Miss` with peer-group coherence checks, after which the Rust middleware (`src/middle/metrics.rs`) verifies every matched definition's derived database conditions before serving.

## Quick Start

```bash
python3 -m pip install -r tools/lookup/requirements.txt

# Start with zero-shot HuggingFace backbone or 3 fine-tuned seed checkpoints from exp/semantic-lookup/
python3 tools/lookup/service.py \
  --host 127.0.0.1 --port 8090 \
  --retriever BAAI/bge-m3 \
  --judges BAAI/bge-reranker-base

# Launch MAVRA middleware connected to the neural lookup service
MAVRA_LOOKUP_URL=http://127.0.0.1:8090 cargo run --release -- serve --mode full --no-etl
```

When `MAVRA_LOOKUP_URL` is unset, `mavra` falls back to lightweight deterministic name/alias lookup so unit tests and small catalogs run without GPU dependencies.
