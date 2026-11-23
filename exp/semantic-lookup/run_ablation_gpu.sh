#!/usr/bin/env bash
# Controlled lookup scaling ablations (GPU only, no external API):
#   1. No peer differences: scale-plain-llm-s13..15 (render = name + text only)
#   2. Matched training density: scale-dc-llm-thin-s13..15 (core phrasings capped at 6 per intent)
# Usage: bash run_ablation_gpu.sh
set -uo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
mkdir -p logs results/lookup_plain results/lookup_thin

if [ ! -f train_26_clean.jsonl ]; then
  "$PY" build_seed_pairs.py || exit 1
fi

EXTRA=train_scale_extra.jsonl,train_scale_llm.jsonl
TRAIN_FILES=train_26_clean.jsonl,$EXTRA
RETR=ft_retriever/bge-m3-cat-llm-s13
MAIN_JUDGES=ft_scale/scale-dc-llm-s13,ft_scale/scale-dc-llm-s14,ft_scale/scale-dc-llm-s15
PLAIN=ft_scale/scale-plain-llm-s13,ft_scale/scale-plain-llm-s14,ft_scale/scale-plain-llm-s15
THIN=ft_scale/scale-dc-llm-thin-s13,ft_scale/scale-dc-llm-thin-s14,ft_scale/scale-dc-llm-thin-s15
GPU0="${GPU0:-0}"
GPU1="${GPU1:-0}"

"$PY" make_thin_core.py train_26_clean.jsonl train_26_thin6.jsonl 6 || exit 1

plain() {  # gpu seed
  CUDA_VISIBLE_DEVICES=$1 "$PY" -u train_scale_ce.py --out "ft_scale/scale-plain-llm-s$2" --seed "$2" \
    --train-extra "$EXTRA" > "logs/train-plain-llm-s$2.log" 2>&1
  local rc=$?; echo "plain s$2 exit $rc"
}
thin() {  # gpu seed
  CUDA_VISIBLE_DEVICES=$1 "$PY" -u train_scale_ce.py --out "ft_scale/scale-dc-llm-thin-s$2" --seed "$2" --def-contrast \
    --train-base train_26_thin6.jsonl --train-extra "$EXTRA" > "logs/train-dc-llm-thin-s$2.log" 2>&1
  local rc=$?; echo "thin s$2 exit $rc"
}

echo "ablation training start"
( plain "$GPU0" 13; plain "$GPU0" 15; thin "$GPU0" 14 ) &
P0=$!
( thin "$GPU1" 13; plain "$GPU1" 14; thin "$GPU1" 15 ) &
P1=$!
wait "$P0" "$P1"
for d in ${PLAIN//,/ } ${THIN//,/ }; do
  [ -f "$d/summary.json" ] || { echo "MISSING $d -- stop"; echo "=== ABLATION FAILED ==="; exit 1; }
done

echo "ablation scoring start"
CUDA_VISIBLE_DEVICES="$GPU0" "$PY" -u score_cache.py --out results/lookup_plain --tuned "$RETR/model" --refreshed-dirs "$MAIN_JUDGES" \
  --train-files "$TRAIN_FILES" --families single_ce_refreshed --plain-dirs "$PLAIN" --skip-timing \
  > logs/score-cache-plain.log 2>&1 &
S0=$!
CUDA_VISIBLE_DEVICES="$GPU1" "$PY" -u score_cache.py --out results/lookup_thin --tuned "$RETR/model" --refreshed-dirs "$THIN" \
  --train-files "$TRAIN_FILES" --skip-timing > logs/score-cache-thin.log 2>&1 &
S1=$!
wait "$S0"; e0=$?
wait "$S1"; e1=$?
echo "scoring exit plain=$e0 thin=$e1"
echo "=== ABLATION DONE ==="
