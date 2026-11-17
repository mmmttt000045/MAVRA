#!/usr/bin/env bash
# README 7: two ablations on the v3 setup (GPU only, no API).
#   7.1 no peer differences: scale-plain-llm-s13..15 (= v3 data, render = name + text)
#   7.2 training density: scale-dc-llm-thin-s13..15 (= v3 data with core phrasings cut to 6 per intent)
# usage: setsid nohup bash run_v3_ablation_gpu.sh > logs/v3-ablation.log 2>&1 < /dev/null &
set -uo pipefail
cd ~/lookup-scale-20261117
PY=/home/mingtai/lookup-pilot-20261110/.venv/bin/python
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
EXTRA=train_scale_extra.jsonl,train_scale_llm.jsonl
TRAIN_FILES=train_26_clean.jsonl,$EXTRA
RETR=ft_retriever/bge-m3-cat-llm-s13
V3=ft_scale/scale-dc-llm-s13,ft_scale/scale-dc-llm-s14,ft_scale/scale-dc-llm-s15
PLAIN=ft_scale/scale-plain-llm-s13,ft_scale/scale-plain-llm-s14,ft_scale/scale-plain-llm-s15
THIN=ft_scale/scale-dc-llm-thin-s13,ft_scale/scale-dc-llm-thin-s14,ft_scale/scale-dc-llm-thin-s15

python3 make_thin_core.py train_26_clean.jsonl train_26_thin6.jsonl 6 || exit 1

plain() {  # gpu seed
  CUDA_VISIBLE_DEVICES=$1 "$PY" -u train_scale_ce.py --out "ft_scale/scale-plain-llm-s$2" --seed "$2" \
    --train-extra "$EXTRA" > "logs/train-plain-llm-s$2.log" 2>&1
  local rc=$?; echo "$(date '+%F %T') plain s$2 exit $rc"
}
thin() {  # gpu seed
  CUDA_VISIBLE_DEVICES=$1 "$PY" -u train_scale_ce.py --out "ft_scale/scale-dc-llm-thin-s$2" --seed "$2" --def-contrast \
    --train-base train_26_thin6.jsonl --train-extra "$EXTRA" > "logs/train-dc-llm-thin-s$2.log" 2>&1
  local rc=$?; echo "$(date '+%F %T') thin s$2 exit $rc"
}

echo "$(date '+%F %T') ablation training start"
( plain 0 13; plain 0 15; thin 0 14 ) &
P0=$!
( thin 1 13; plain 1 14; thin 1 15 ) &
P1=$!
wait "$P0" "$P1"
for d in ${PLAIN//,/ } ${THIN//,/ }; do
  [ -f "$d/summary.json" ] || { echo "MISSING $d -- stop"; echo "=== V3 ABLATION FAILED ==="; exit 1; }
done

echo "$(date '+%F %T') ablation scoring start"
CUDA_VISIBLE_DEVICES=0 "$PY" -u score_cache_v2.py --out results_v3_plain --tuned "$RETR/model" --refreshed-dirs "$V3" \
  --train-files "$TRAIN_FILES" --families single_ce_refreshed --plain-dirs "$PLAIN" --skip-timing \
  > logs/score-cache-v3-plain.log 2>&1 &
S0=$!
CUDA_VISIBLE_DEVICES=1 "$PY" -u score_cache_v2.py --out results_v3_thin --tuned "$RETR/model" --refreshed-dirs "$THIN" \
  --train-files "$TRAIN_FILES" --skip-timing > logs/score-cache-v3-thin.log 2>&1 &
S1=$!
wait "$S0"; e0=$?
wait "$S1"; e1=$?
echo "$(date '+%F %T') scoring exit plain=$e0 thin=$e1"
echo "=== V3 ABLATION DONE ==="
