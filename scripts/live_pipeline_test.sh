#!/usr/bin/env bash
# Live end-to-end test of the alerting pipeline WITHOUT Docker:
#   demo-app -> Prometheus (scrape + rules) -> Alertmanager (routing + inhibition) -> webhook
#
# Needs the prometheus and alertmanager binaries on PATH (or PROM_BIN / AM_BIN),
# plus: pip install flask prometheus-client gunicorn
# Takes ~3.5 minutes because alerts have real "for:" durations.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
PROM_BIN="${PROM_BIN:-prometheus}"; AM_BIN="${AM_BIN:-alertmanager}"
W=$(mktemp -d); PIDS=()
cleanup() { kill "${PIDS[@]}" 2>/dev/null || true; rm -rf "$W"; }
trap cleanup EXIT
q() { curl -s "127.0.0.1:19090/api/v1/$1"; }
check() { local d="$1"; shift; if "$@"; then echo "PASS  $d"; else echo "FAIL  $d" >&2; exit 1; fi; }

# localhost variants of the real configs (faster intervals, same rules)
sed -e 's#demo-app:8000#127.0.0.1:18000#' -e 's#alertmanager:9093#127.0.0.1:19093#' \
    -e "s#/etc/prometheus/rules#$PWD/prometheus/rules#" -e 's#localhost:9090#127.0.0.1:19090#' \
    -e '/job_name: node/,$d' -e 's/_interval: 15s/_interval: 5s/' prometheus/prometheus.yml > "$W/prom.yml"
sed -e 's#webhook-logger:9095#127.0.0.1:19095#' -e 's/group_wait: 30s/group_wait: 5s/' \
    alertmanager/alertmanager.yml > "$W/am.yml"
sed 's/9095/19095/g' webhook-logger/app.py > "$W/receiver.py"

(cd demo-app && exec python3 -m gunicorn -b 127.0.0.1:18000 -w 1 --threads 8 app:app) > "$W/app.log" 2>&1 &
APP=$!; PIDS+=("$APP")
python3 -u "$W/receiver.py" > "$W/hook.log" 2>&1 & PIDS+=("$!")
"$AM_BIN" --config.file="$W/am.yml" --storage.path="$W/am" --web.listen-address=127.0.0.1:19093 \
  --cluster.listen-address= > "$W/am.log" 2>&1 & PIDS+=("$!")
"$PROM_BIN" --config.file="$W/prom.yml" --storage.tsdb.path="$W/tsdb" \
  --web.listen-address=127.0.0.1:19090 > "$W/prom.log" 2>&1 & PIDS+=("$!")
sleep 6

( for _ in $(seq 600); do curl -s -o /dev/null 127.0.0.1:18000/api/orders
    curl -s -o /dev/null -X POST 127.0.0.1:18000/api/orders; sleep 0.1; done ) & PIDS+=("$!")
sleep 20
check "Prometheus scrapes the demo app" bash -c "curl -s 127.0.0.1:19090/api/v1/targets | grep -q '\"health\":\"up\"'"

curl -s -X POST "127.0.0.1:18000/chaos/errors?rate=0.4" >/dev/null
sleep 45
ratio=$(q 'query?query=service:http_errors:ratio5m' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["result"][0]["value"][1])')
check "recording rule error ratio = $ratio (> 0.05)" python3 -c "import sys; sys.exit(0 if float('$ratio') > 0.05 else 1)"
check "Watchdog delivered to heartbeat receiver" grep -q "Watchdog" "$W/hook.log"

kill "$APP"; sleep 110
check "ServiceDown paged on-call" grep -q "\[oncall\] FIRING   critical ServiceDown" "$W/hook.log"
check "HighErrorRate inhibited while the service is down" bash -c "curl -s 127.0.0.1:19093/api/v2/alerts | python3 -c '
import json, sys
a = {x[\"labels\"][\"alertname\"]: x[\"status\"][\"state\"] for x in json.load(sys.stdin)}
sys.exit(0 if a.get(\"HighErrorRate\") == \"suppressed\" else 1)'"
echo "--- webhook received ---"; cat "$W/hook.log"
