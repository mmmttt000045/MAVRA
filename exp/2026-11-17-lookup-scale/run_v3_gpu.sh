#!/usr/bin/env bash
# Revision v3 (README section 5) on server200: same recipes as v2, training data adds train_scale_llm.jsonl.
#   GPU0: judge s13 -> judge s15      GPU1: retriever s13 -> judge s14
#   then the score cache on the main 390 (GPU0, with timing) and the fresh 204 (GPU1).
# usage: setsid nohup bash run_v3_gpu.sh > logs/v3-pipeline.log 2>&1 < /dev/null &
set -uo pipefail
cd ~/lookup-scale-20261117
PY=/home/mingtai/lookup-pilot-20261110/.venv/bin/python
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
EXTRA=train_scale_extra.jsonl,train_scale_llm.jsonl
TRAIN_FILES=train_26_clean.jsonl,$EXTRA
JUDGES=ft_scale/scale-dc-llm-s13,ft_scale/scale-dc-llm-s14,ft_scale/scale-dc-llm-s15
RETR=ft_retriever/bge-m3-cat-llm-s13

judge() {  # gpu seed
  CUDA_VISIBLE_DEVICES=$1 "$PY" -u train_scale_ce.py --out "ft_scale/scale-dc-llm-s$2" --seed "$2" --def-contrast \
    --train-extra "$EXTRA" > "logs/train-dc-llm-s$2.log" 2>&1
  local rc=$?; echo "$(date '+%F %T') judge s$2 exit $rc"
}

echo "$(date '+%F %T') v3 training start"
( judge 0 13; judge 0 15 ) &
P0=$!
(
  CUDA_VISIBLE_DEVICES=1 "$PY" -u train_retriever.py --out "$RETR" --seed 13 --train-extra "$EXTRA" \
    > logs/train-retriever-llm-s13.log 2>&1
  rc=$?; echo "$(date '+%F %T') retriever exit $rc"
  judge 1 14
) &
P1=$!
wait "$P0" "$P1"

for d in ${JUDGES//,/ } "$RETR"; do
  if [ ! -f "$d/summary.json" ]; then echo "MISSING $d/summary.json -- stop"; echo "=== V3 PIPELINE FAILED ==="; exit 1; fi
done

echo "$(date '+%F %T') v3 score cache start"
CUDA_VISIBLE_DEVICES=0 "$PY" -u score_cache_v2.py --out results_v3 --tuned "$RETR/model" \
  --refreshed-dirs "$JUDGES" --train-files "$TRAIN_FILES" > logs/score-cache-v3.log 2>&1 &
S0=$!
CUDA_VISIBLE_DEVICES=1 "$PY" -u score_cache_v2.py --out results_v3_fresh --tuned "$RETR/model" \
  --refreshed-dirs "$JUDGES" --train-files "$TRAIN_FILES" \
  --qsets glm_scale=requests_glm_scale.json --skip-timing > logs/score-cache-v3-fresh.log 2>&1 &
S1=$!
wait "$S0"; e0=$?
wait "$S1"; e1=$?
echo "$(date '+%F %T') score cache exit main=$e0 fresh=$e1"
echo "=== V3 PIPELINE DONE ==="
