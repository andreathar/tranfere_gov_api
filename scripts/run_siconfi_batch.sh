#!/bin/bash
# Batch SICONFI enrichment — all UFs in parallel tmux waves.
# The enricher auto-skips already-enriched municipalities.
# API hangs after ~80 requests/session, so --limit 70 per wave.
# Usage: ./src/run_siconfi_batch.sh
set -euo pipefail

cd "$(dirname "$0")/.."
VENV="source .venv/bin/activate"
LOG_DIR="output/logs"
BATCH=70
MAX_PARALLEL=5
DELAY=5

declare -a UFS=(MG SP RS BA PR SC GO PI PB MA PA PE CE RN MT TO RJ AL MS ES SE AM RO AP AC RR)

echo "=== SICONFI Batch Enrichment ==="
echo "UFs: ${#UFS[@]} | Batch: $BATCH munis | Parallel: $MAX_PARALLEL"
echo ""

SESSION=0
ACTIVE=()

wait_for_slot() {
  while [ ${#ACTIVE[@]} -ge $MAX_PARALLEL ]; do
    CLEAN=()
    for s in "${ACTIVE[@]}"; do
      tmux has-session -t "$s" 2>/dev/null && CLEAN+=("$s")
    done
    ACTIVE=("${CLEAN[@]}")
    [ ${#ACTIVE[@]} -ge $MAX_PARALLEL ] && sleep 15
  done
}

for uf in "${UFS[@]}"; do
  wait_for_slot
  SESSION=$((SESSION + 1))
  SID="siconfi_${uf}"
  LOG="$LOG_DIR/siconfi_${uf}.log"
  echo "[$SESSION/${#UFS[@]}] $uf → $SID"
  tmux new-session -d -s "$SID" \
    "$VENV && python3 -m src.enrichers.siconfi --uf $uf --limit $BATCH 2>&1 | tee '$LOG'"
  ACTIVE+=("$SID")
  sleep $DELAY
done

echo ""
echo "=== All $SESSION sessions launched ==="
echo "Monitor: tmux ls | grep siconfi"
echo ""

while true; do
  CLEAN=()
  for s in "${ACTIVE[@]}"; do
    tmux has-session -t "$s" 2>/dev/null && CLEAN+=("$s")
  done
  ACTIVE=("${CLEAN[@]}")
  [ ${#ACTIVE[@]} -eq 0 ] && break
  echo "  ... ${#ACTIVE[@]} sessions running"
  sleep 30
done

echo ""
echo "=== Wave complete ==="
source .venv/bin/activate
python3 -c "
import psycopg2
conn = psycopg2.connect(host='127.0.0.1', dbname='transferegov_db', user='cognee', password='cognee')
cur = conn.cursor()
cur.execute('SELECT COUNT(DISTINCT municipio_id) FROM municipios_financeiro')
done = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM municipios_ibge')
total = cur.fetchone()[0]
print(f'Coverage: {done}/{total} ({done/total*100:.1f}%)')
cur.execute('''
    SELECT m.uf, COUNT(DISTINCT m.municipio_id) AS t,
           COUNT(DISTINCT mf.municipio_id) AS d,
           ROUND(COUNT(DISTINCT mf.municipio_id)::numeric / COUNT(DISTINCT m.municipio_id) * 100, 1) AS p
    FROM municipios_ibge m
    LEFT JOIN municipios_financeiro mf ON m.municipio_id = mf.municipio_id
    GROUP BY m.uf
    HAVING COUNT(DISTINCT mf.municipio_id) < COUNT(DISTINCT m.municipio_id)
    ORDER BY (COUNT(DISTINCT m.municipio_id) - COUNT(DISTINCT mf.municipio_id)) DESC
''')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[2]}/{row[1]} ({row[3]}%)')
conn.close()
"
