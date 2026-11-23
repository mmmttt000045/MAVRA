#!/usr/bin/env bash
# Train the catalog-tuned bge-m3 retriever and three peer-difference XLM-R judges,
# then build the score caches on the 390 main requests and 204 held-out paraphrases.
# Usage: bash run_gpu.sh
set -uo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
mkdir -p logs results/lookup results/lookup_fresh

if [ ! -f train_26_clean.jsonl ]; then
  "$PY" build_seed_pairs.py || exit 1
fi

EXTRA=train_scale_extra.jsonl,train_scale_llm.jsonl
TRAIN_FILES=train_26_clean.jsonl,$EXTRA
JUDGES=ft_scale/scale-dc-llm-s13,ft_scale/scale-dc-llm-s14,ft_scale/scale-dc-llm-s15
RETR=ft_retriever/bge-m3-cat-llm-s13
GPU0="${GPU0:-0}"
GPU1="${GPU1:-0}"

judge() {  # gpu seed
  CUDA_VISIBLE_DEVICES=$1 "$PY" -u train_scale_ce.py --out "ft_scale/scale-dc-llm-s$2" --seed "$2" --def-contrast \
    --train-extra "$EXTRA" > "logs/train-dc-llm-s$2.log" 2>&1
  local rc=$?; echo "judge s$2 exit $rc"
}

echo "training start"
( judge "$GPU0" 13; judge "$GPU0" 15 ) &
P0=$!
(
  CUDA_VISIBLE_DEVICES="$GPU1" "$PY" -u train_retriever.py --out "$RETR" --seed 13 --train-extra "$EXTRA" \
    > logs/train-retriever-llm-s13.log 2>&1
  rc=$?; echo "retriever exit $rc"
  judge "$GPU1" 14
) &
P1=$!
wait "$P0" "$P1"

for d in ${JUDGES//,/ } "$RETR"; do
  if [ ! -f "$d/summary.json" ]; then echo "MISSING $d/summary.json -- stop"; echo "=== PIPELINE FAILED ==="; exit 1; fi
done

echo "score cache start"
CUDA_VISIBLE_DEVICES="$GPU0" "$PY" -u score_cache.py --out results/lookup --tuned "$RETR/model" \
  --refreshed-dirs "$JUDGES" --train-files "$TRAIN_FILES" > logs/score-cache-main.log 2>&1 &
S0=$!
CUDA_VISIBLE_DEVICES="$GPU1" "$PY" -u score_cache.py --out results/lookup_fresh --tuned "$RETR/model" \
  --refreshed-dirs "$JUDGES" --train-files "$TRAIN_FILES" \
  --qsets glm_scale=requests_glm_scale.json --skip-timing > logs/score-cache-fresh.log 2>&1 &
S1=$!
wait "$S0"; e0=$?
wait "$S1"; e1=$?
echo "score cache exit main=$e0 fresh=$e1"
echo "=== PIPELINE DONE ==="
