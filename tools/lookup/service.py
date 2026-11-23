#!/usr/bin/env python3
"""MAVRA Semantic Definition Lookup Service (`POST /resolve`, `GET /health`).

Implements Section 4.3 semantic metric resolution for large shared catalogs:
  1. Dense candidate recall (`K = 8`, widened to `K_max = 32` for absence checks) with `BAAI/bge-m3`.
  2. Structured business-attribute projection B(I) = (F, e, AGG_e, tau, phi) and bounded peer-difference
     rendering scored by a 3-model 12-layer XLM-RoBERTa cross-encoder ensemble (`BAAI/bge-reranker-base`
     or fine-tuned seed checkpoints via `--judges`).
  3. Selective `(0.10, 0.90)` decision routing into `Hit`, `Diffs`, `Refer`, and `Miss` with peer-group
     coherence verification and close-neighbor cosine screening (`sigma = 0.60`).

Start the service and point MAVRA at it via `MAVRA_LOOKUP_URL=http://127.0.0.1:8090`:
  python3 tools/lookup/service.py --host 127.0.0.1 --port 8090 \
      --retriever BAAI/bge-m3 --judges BAAI/bge-reranker-base
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

DEFAULT_FACET_NAMES = {
    "channel": "Channel",
    "subject": "Fact",
    "grain": "Grain",
    "measure": "Measure",
    "time": "Time",
    "category": "Category",
    "filters": "Filters",
}


def facet_value(defn: dict[str, Any], slot: str) -> str:
    val = (defn.get("facets") or {}).get(slot)
    if val:
        return str(val)
    return "all" if slot == "category" else "none"


def base_text(defn: dict[str, Any]) -> str:
    aliases = defn.get("aliases") or []
    alias_part = f" ({', '.join(aliases)})" if aliases else ""
    return f"{defn['name']}{alias_part}: {defn.get('text', '')}"


def render_with_peer_diffs(defn: dict[str, Any], pool: list[dict[str, Any]], facet_names: dict[str, str]) -> str:
    """Render candidate definition alongside its structured facets and up to 4 closest catalog peers."""
    out = base_text(defn)
    facets = defn.get("facets") or {}
    shown_slots = [s for s in facet_names if facets.get(s) or s == "category"]
    if shown_slots:
        out += " | Facets: " + "; ".join(f"{facet_names[s]}={facet_value(defn, s)}" for s in shown_slots)

    def peer_bucket(entry: dict[str, Any]) -> tuple[Any, Any]:
        ef = entry.get("facets") or {}
        return (ef.get("channel"), ef.get("subject"))

    peers = [
        e for e in pool
        if e.get("id") != defn.get("id") and (peer_bucket(e) == peer_bucket(defn) or e.get("name") == defn.get("name"))
    ]
    peers.sort(
        key=lambda e: (
            e.get("name") != defn.get("name"),
            (e.get("facets") or {}).get("category") != facets.get("category"),
            str(e.get("id", "")),
        )
    )
    diffs = []
    for peer in peers[:4]:
        who = "homonymous peer" if peer.get("name") == defn.get("name") else f"'{peer.get('name')}'"
        changed = [s for s in facet_names if facet_value(defn, s) != facet_value(peer, s)]
        if changed:
            detail = ", ".join(
                f"{facet_names[s]}={facet_value(peer, s)} (this={facet_value(defn, s)})" for s in changed
            )
            diffs.append(f"{who}: {detail}")
    if diffs:
        out += " | Peer differences: " + "; ".join(diffs)
    return out


def explain_differences(ids: list[str], by_id: dict[str, dict[str, Any]], facet_names: dict[str, str]) -> str:
    if len(ids) < 2:
        return ""
    chosen = [by_id[i] for i in ids if i in by_id]
    varying = [s for s in facet_names if len({facet_value(d, s) for d in chosen}) > 1]
    return "; ".join(
        f"{facet_names[s]}: " + " / ".join(f"{d['name']} ({d['id']})={facet_value(d, s)}" for d in chosen)
        for s in varying
    )


def coherence_group(defn: dict[str, Any]) -> tuple[Any, Any, Any]:
    facets = defn.get("facets") or {}
    return (facets.get("subject"), facets.get("category"), facets.get("channel") or "all")


def route_candidates(
    cand_ids: list[str],
    cosines: list[float],
    scores: list[float],
    by_id: dict[str, dict[str, Any]],
    facet_names: dict[str, str],
    top_k: int = 8,
    lo: float = 0.10,
    hi: float = 0.90,
    sigma: float = 0.60,
    coherence: bool = True,
    widen: bool = True,
) -> dict[str, Any]:
    """Apply Section 4.3 selective thresholds `(lo, hi)` to produce `Hit`, `Diffs`, `Refer`, or `Miss`."""
    if not cand_ids:
        return {"decision": "Miss", "keys": [], "differences": "", "message": "No published metric definitions match."}

    c_top = cand_ids[:top_k]
    s_top = scores[:top_k]
    accepted = [cid for cid, sc in zip(c_top, s_top) if sc >= hi]
    uncertain = [cid for cid, sc in zip(c_top, s_top) if lo <= sc < hi]

    if uncertain:
        picked = sorted(set(accepted + uncertain))
        diffs = explain_differences(picked, by_id, facet_names)
        return {
            "decision": "Refer",
            "keys": picked,
            "differences": diffs,
            "message": "Borderline candidate definition(s) in [0.10, 0.90); confirm scope before execution.",
        }

    if accepted:
        picked = sorted(set(accepted))
        if len(picked) == 1:
            return {"decision": "Hit", "keys": picked, "differences": "", "message": ""}
        if coherence and len({coherence_group(by_id[i]) for i in picked if i in by_id}) > 1:
            diffs = explain_differences(picked, by_id, facet_names)
            return {
                "decision": "Refer",
                "keys": picked,
                "differences": diffs,
                "message": "Multiple cross-group definitions scored above threshold; confirm intended business entity/fact.",
            }
        diffs = explain_differences(picked, by_id, facet_names)
        return {
            "decision": "Diffs",
            "keys": picked,
            "differences": diffs,
            "message": f"Multiple valid definitions ({len(picked)}) differ on unstated business attributes.",
        }

    if widen:
        widened = [cid for cid, sc in zip(cand_ids[top_k:], scores[top_k:]) if sc >= lo]
        if widened:
            picked = sorted(set(widened))
            diffs = explain_differences(picked, by_id, facet_names)
            return {
                "decision": "Refer",
                "keys": picked,
                "differences": diffs,
                "message": "Widened recall (ranks 9..32) found plausible candidate definition(s); confirm before execution.",
            }

    if cosines and cosines[0] >= sigma:
        picked = [cand_ids[0]]
        return {
            "decision": "Refer",
            "keys": picked,
            "differences": "",
            "message": "No exact facet match, but a close catalog neighbor exists; confirm whether it applies.",
        }

    return {"decision": "Miss", "keys": [], "differences": "", "message": "No matching metric definition in catalog."}


class NeuralLookupEngine:
    """Thread-safe dense BGE-M3 + 3-Cross-Encoder (`XLM-RoBERTa` / `bge-reranker-base`) resolver."""

    def __init__(
        self,
        retriever_model: str,
        judge_models: list[str],
        device: str = "auto",
        top_k: int = 8,
        k_max: int = 32,
        lo: float = 0.10,
        hi: float = 0.90,
        sigma: float = 0.60,
        preloaded_catalog: dict[str, Any] | None = None,
    ) -> None:
        import numpy as np
        import torch
        from sentence_transformers import SentenceTransformer
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._np = np
        self._torch = torch
        self.device = ("cuda" if torch.cuda.is_available() else "cpu") if device == "auto" else device
        self.top_k = top_k
        self.k_max = k_max
        self.lo = lo
        self.hi = hi
        self.sigma = sigma
        self._lock = threading.Lock()
        self._emb_cache: dict[str, Any] = {}
        self.preloaded_defs = (preloaded_catalog or {}).get("definitions") or []
        self.facet_names = (preloaded_catalog or {}).get("facet_names") or DEFAULT_FACET_NAMES

        self.retriever = SentenceTransformer(retriever_model, device=self.device)
        self.judges = []
        for path in judge_models:
            tok = AutoTokenizer.from_pretrained(path)
            mdl = AutoModelForSequenceClassification.from_pretrained(path).to(self.device)
            mdl.eval()
            self.judges.append((tok, mdl))

    def _embed_definitions(self, defs: list[dict[str, Any]]) -> Any:
        np = self._np
        texts = [base_text(d) for d in defs]
        keys = [hashlib.sha256(t.encode("utf-8")).hexdigest() for t in texts]
        missing_idx = [i for i, k in enumerate(keys) if k not in self._emb_cache]
        if missing_idx:
            vecs = self.retriever.encode(
                [texts[i] for i in missing_idx],
                normalize_embeddings=True,
                batch_size=64,
                show_progress_bar=False,
            )
            for i, vec in zip(missing_idx, vecs):
                self._emb_cache[keys[i]] = vec
        return np.vstack([self._emb_cache[k] for k in keys])

    def _score_pairs(self, query: str, rendered_candidates: list[str]) -> list[float]:
        if not rendered_candidates:
            return []
        torch = self._torch
        np = self._np
        pairs = [(query, text) for text in rendered_candidates]
        per_judge = []
        with torch.inference_mode():
            for tok, mdl in self.judges:
                enc = tok(pairs, padding=True, truncation=True, max_length=384, return_tensors="pt").to(self.device)
                logits = mdl(**enc).logits.squeeze(-1)
                if logits.ndim == 0:
                    logits = logits.unsqueeze(0)
                probs = torch.sigmoid(logits).detach().cpu().numpy()
                per_judge.append(probs)
        mean_scores = np.mean(per_judge, axis=0)
        return [float(x) for x in mean_scores]

    def resolve(self, payload: dict[str, Any]) -> dict[str, Any]:
        query = str(payload.get("query") or "").strip()
        defs = payload.get("definitions") if payload.get("definitions") is not None else self.preloaded_defs
        facet_names = payload.get("facet_names") or self.facet_names
        if not query or not defs:
            return {"decision": "Miss", "keys": [], "differences": "", "message": "Empty query or catalog.", "scores": []}

        with self._lock:
            dvecs = self._embed_definitions(defs)
            qvec = self.retriever.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
            sims = dvecs @ qvec
            limit = min(len(defs), self.k_max)
            order = self._np.argsort(-sims)[:limit]
            cand_defs = [defs[int(i)] for i in order]
            cand_ids = [str(d["id"]) for d in cand_defs]
            cosines = [round(float(sims[int(i)]), 5) for i in order]
            rendered = [render_with_peer_diffs(d, defs, facet_names) for d in cand_defs]
            scores = self._score_pairs(query, rendered)

        by_id = {str(d["id"]): d for d in defs}
        out = route_candidates(
            cand_ids,
            cosines,
            scores,
            by_id,
            facet_names,
            top_k=self.top_k,
            lo=self.lo,
            hi=self.hi,
            sigma=self.sigma,
        )
        out["scores"] = [
            {"id": cid, "cosine": cos, "score": round(sc, 5)}
            for cid, cos, sc in zip(cand_ids[: self.top_k], cosines[: self.top_k], scores[: self.top_k])
        ]
        return out


def make_handler(engine: NeuralLookupEngine):
    class LookupHandler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: dict[str, Any]) -> None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._send(200, {"ok": True, "device": engine.device, "judges": len(engine.judges)})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/resolve":
                self._send(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length or 0).decode("utf-8") or "{}")
                self._send(200, engine.resolve(payload))
            except Exception as exc:  # noqa: BLE001
                self._send(400, {"error": str(exc)})

        def log_message(self, fmt: str, *args: Any) -> None:
            return

    return LookupHandler


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", default=os.environ.get("MAVRA_LOOKUP_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("MAVRA_LOOKUP_PORT", "8090")))
    ap.add_argument("--retriever", default=os.environ.get("MAVRA_RETRIEVER_MODEL", "BAAI/bge-m3"))
    ap.add_argument(
        "--judges",
        default=os.environ.get("MAVRA_JUDGE_MODELS", "BAAI/bge-reranker-base"),
        help="Comma-separated HuggingFace model IDs or fine-tuned 3-seed checkpoint directories (12-layer XLM-RoBERTa)",
    )
    ap.add_argument("--catalog", type=Path, default=None, help="Optional preloaded catalog JSON (e.g., catalog_1000.json)")
    ap.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    ap.add_argument("--top-k", type=int, default=8)
    ap.add_argument("--k-max", type=int, default=32)
    ap.add_argument("--lo", type=float, default=0.10)
    ap.add_argument("--hi", type=float, default=0.90)
    ap.add_argument("--sigma", type=float, default=0.60)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8")) if args.catalog else None
    judges = [m.strip() for m in args.judges.split(",") if m.strip()]
    engine = NeuralLookupEngine(
        retriever_model=args.retriever,
        judge_models=judges,
        device=args.device,
        top_k=args.top_k,
        k_max=args.k_max,
        lo=args.lo,
        hi=args.hi,
        sigma=args.sigma,
        preloaded_catalog=catalog,
    )
    server = ThreadingHTTPServer((args.host, args.port), make_handler(engine))
    print(f"MAVRA lookup service listening on http://{args.host}:{args.port} (device={engine.device}, judges={len(judges)})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
