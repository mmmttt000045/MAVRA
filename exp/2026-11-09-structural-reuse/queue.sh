#!/bin/bash
# Structural-variation population study (README.md). Run on noctis from /root/agentdb-struct.
# usage: queue.sh OUT TAG...   (TAG = r<run>-<mode>, e.g. r1-metric-global-snap r1-paper-tecod)
# SMOKE=1: 2 agents x 4 questions (MAVRA 4 x 7), results not used; SIZE overrides (e.g. "--agents 4 --per-agent 7").
# CONC (default 8): cells at a time.
# MIN_FREE (default 8): free GB below which no new cell starts. The TeCoD selection server (port 19532, ~35 GB) and the
# population TeCoD service (port 19541) start when a paper-tecod tag is present and stop at the end.
cd /root/agentdb-struct
OUT=$1; shift
mkdir -p "$OUT"
set -a; . ./.env; set +a
export DEEPSEEK_REASONING_EFFORT=high NO_PROXY=127.0.0.1,localhost
free_gb() { df -BG --output=avail / | tail -1 | tr -dc 0-9; }
wait_port() { for i in $(seq 120); do curl -s -m 5 "http://127.0.0.1:$1/health" | grep -q true && return 0; sleep 10; done; return 1; }
SERVICES=()
if printf '%s\n' "$@" | grep -q -- '-paper-tecod$'; then
  ( env HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false TECOD_THREADS=24 \
      /root/agentdb-mid/results/ext/venv-tecod/bin/python -u tools/relbench/tecod_server.py \
      --models /root/agentdb-mid/results/ext/tecod-models --port 19532 >> "$OUT/tecod-server.log" 2>&1 ) &
  SERVICES+=($!)
  wait_port 19532 || { echo "$(date '+%F %T') tecod server did not start" >> "$OUT/queue.log"; exit 1; }
  ( env PYTHONPATH=/root/agentdb-mid/.pydeps-relbench python3 -u exp/2026-11-09-structural-reuse/tecod-service.py \
      --port 19541 --tecod-url http://127.0.0.1:19532/tecod --out "$OUT/tecod-memory" >> "$OUT/tecod-service.log" 2>&1 ) &
  SERVICES+=($!)
  wait_port 19541 || { echo "$(date '+%F %T') tecod service did not start" >> "$OUT/queue.log"; exit 1; }
fi
for tag in "$@"; do
  r=${tag%%-*}; r=${r#r}; mode=${tag#*-}
  ls "$OUT/$tag"/metric-*/report.json > /dev/null 2>&1 && continue
  while [ "$(jobs -rp | wc -l)" -ge "$(( ${CONC:-8} + ${#SERVICES[@]} ))" ] || [ "$(free_gb)" -lt "${MIN_FREE:-8}" ]; do sleep 30; done
  if [ -n "$SIZE" ]; then
    size="$SIZE"
  elif [ "$SMOKE" = 1 ]; then
    if [ "$mode" = metric-global-snap ]; then size="--agents 4 --per-agent 7"; else size="--agents 2 --per-agent 4"; fi
  else
    size="--agents 16 --per-agent 7"
  fi
  mkdir -p "$OUT/$tag"
  echo "$(date '+%F %T') start $tag (free $(free_gb) GB)" >> "$OUT/queue.log"
  ( env FIG6_MEMORY_URL=http://127.0.0.1:19541/memory FIG6_CELL_KEY="pop-r$r-tecod" \
      ./target/release/agentdb-mid --pool 8 --out "$OUT/$tag" metric-bench \
      --agent deepseek --extractor deepseek --spec exp/2026-10-11-generality/schemas/tpcds.json \
      --defs exp/2026-11-09-structural-reuse/tpcds-defs.json --metrics M1,M2,M3,M4,M5 --phrasings named \
      --repeats 1 --first-repeat "$r" --question-set v3 --sql-timeout-secs 120 --modes "$mode" --population $size \
      --returning 0 --concurrency 1 --trace > "$OUT/$tag.log" 2>&1 < /dev/null
    echo "$(date '+%F %T') exit $? $tag" >> "$OUT/queue.log" ) &
  sleep 20
done
while [ "$(jobs -rp | wc -l)" -gt "${#SERVICES[@]}" ]; do sleep 30; done
for p in "${SERVICES[@]}"; do pkill -P "$p" 2>/dev/null; kill "$p" 2>/dev/null; done
echo "$(date '+%F %T') all done: $*" >> "$OUT/queue.log"
