#!/usr/bin/env bash
# Trigger demo scenarios against the running stack.
#   ./scripts/chaos.sh errors [rate]   | latency [ms] | down | up | reset | status
set -euo pipefail
APP="${APP_URL:-http://localhost:8000}"
case "${1:-status}" in
  errors)  curl -fsS -X POST "$APP/chaos/errors?rate=${2:-0.3}"; echo ;;
  latency) curl -fsS -X POST "$APP/chaos/latency?ms=${2:-800}"; echo ;;
  reset)   curl -fsS -X POST "$APP/chaos/reset"; echo ;;
  down)    docker compose stop demo-app ;;
  up)      docker compose start demo-app ;;
  status)
    echo "-- firing alerts (Alertmanager) --"
    curl -fsS localhost:9093/api/v2/alerts | python3 -c '
import json, sys
for a in json.load(sys.stdin):
    print(f"{a[\"status\"][\"state\"]:10} {a[\"labels\"].get(\"severity\",\"\"):9} {a[\"labels\"][\"alertname\"]}")'
    echo "-- delivered (webhook-logger) --"
    curl -fsS localhost:9095/ | python3 -c '
import json, sys
for a in json.load(sys.stdin)[-10:]:
    print(a["received_at"], a["receiver"], a["status"], a["alertname"])' ;;
  *) echo "usage: $0 errors|latency|reset|down|up|status" >&2; exit 2 ;;
esac
