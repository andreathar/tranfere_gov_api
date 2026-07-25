#!/bin/bash
# Sequential SICONFI enrichment — all UFs in one session.
# The enricher auto-skips already-enriched municipalities.
# API hangs after ~80 requests, so we process 70 per UF then move on.
# Multiple passes needed for large UFs (MG, SP, etc.).
set -euo pipefail

cd "$(dirname "$0")/.."
source .venv/bin/activate
BATCH=70
PASS=0

while true; do
  PASS=$((PASS + 1))
  echo "=== Pass $PASS ==="

  DONE_BEFORE=$(python3 -c "
import psycopg2
conn = psycopg2.connect(host='127.0.0.1', dbname='transferegov_db', user='cognee', password='cognee')
cur = conn.cursor()
cur.execute('SELECT COUNT(DISTINCT municipio_id) FROM municipios_financeiro')
print(cur.fetchone()[0])
conn.close()
")

  python3 -m src.enrichers.siconfi --limit $BATCH 2>&1 | tail -5

  DONE_AFTER=$(python3 -c "
import psycopg2
conn = psycopg2.connect(host='127.0.0.1', dbname='transferegov_db', user='cognee', password='cognee')
cur = conn.cursor()
cur.execute('SELECT COUNT(DISTINCT municipio_id) FROM municipios_financeiro')
print(cur.fetchone()[0])
conn.close()
")

  NEW=$((DONE_AFTER - DONE_BEFORE))
  echo "Pass $PASS: +$NEW → $DONE_AFTER/5570"

  if [ "$NEW" -eq 0 ]; then
    echo "No new data. Stopping."
    break
  fi

  TOTAL=$(python3 -c "
import psycopg2
conn = psycopg2.connect(host='127.0.0.1', dbname='transferegov_db', user='cognee', password='cognee')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM municipios_ibge')
print(cur.fetchone()[0])
conn.close()
")
  if [ "$DONE_AFTER" -ge "$TOTAL" ]; then
    echo "All municipalities enriched!"
    break
  fi
done

echo ""
echo "=== Final ==="
python3 -c "
import psycopg2
conn = psycopg2.connect(host='127.0.0.1', dbname='transferegov_db', user='cognee', password='cognee')
cur = conn.cursor()
cur.execute('SELECT COUNT(DISTINCT municipio_id) FROM municipios_financeiro')
done = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM municipios_ibge')
total = cur.fetchone()[0]
print(f'Coverage: {done}/{total} ({done/total*100:.1f}%)')
conn.close()
"
