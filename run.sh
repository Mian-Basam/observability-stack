#!/usr/bin/env bash
# Observability Stack - one entry point for every common task.
#
#   ./run.sh                 show help
#   ./run.sh start           Prometheus + Grafana + Loki + Alertmanager + demo app
#   ./run.sh chaos errors    trigger an incident and watch the alerts fire
#   ./run.sh stop            stop everything (data is kept)
#
# Run "./run.sh help" for the full list.
set -euo pipefail
cd "$(dirname "$0")"

# Use tools installed by ../install.sh (shared ../.venv and ~/.local/bin); nothing to activate.
[[ -x ../.venv/bin/python ]] && PATH="$(cd .. && pwd)/.venv/bin:$PATH"
PATH="$HOME/.local/bin:$PATH"; export PATH

c_ok=$'\e[32m'; c_err=$'\e[31m'; c_dim=$'\e[2m'; c_off=$'\e[0m'
[[ -t 1 && -z "${NO_COLOR:-}" ]] || { c_ok=""; c_err=""; c_dim=""; c_off=""; }
say()  { printf '%s>>%s %s\n' "$c_ok" "$c_off" "$*"; }
die()  { printf '%sERROR:%s %s\n' "$c_err" "$c_off" "$*" >&2; exit 1; }
need() { local m=(); for t in "$@"; do command -v "$t" >/dev/null || m+=("$t"); done
         ((${#m[@]} == 0)) || die "missing tool(s): ${m[*]}  (fix: ./run.sh install-deps)"; }
need_docker() {
  need docker
  docker compose version >/dev/null 2>&1 || die "Docker Compose v2 plugin not found ('docker compose')"
  docker info >/dev/null 2>&1 || die "Docker daemon is not running (start Docker Desktop / dockerd)"
}
urls() {
  cat <<EOF
  Grafana        http://localhost:3000   (admin / admin)
  Prometheus     http://localhost:9090
  Alertmanager   http://localhost:9093
  Alert receiver http://localhost:9095
  Demo app       http://localhost:8000
EOF
}

doctor() {
  local rc=0
  for t in docker curl python3 promtool amtool yamllint ruff pytest prometheus alertmanager; do
    if command -v "$t" >/dev/null; then printf '  %sok%s       %s\n' "$c_ok" "$c_off" "$t"
    else printf '  %smissing%s  %s\n' "$c_err" "$c_off" "$t"; rc=1; fi
  done
  docker compose version >/dev/null 2>&1 && printf '  %sok%s       docker compose\n' "$c_ok" "$c_off" \
    || { printf '  %smissing%s  docker compose v2\n' "$c_err" "$c_off"; rc=1; }
  docker info >/dev/null 2>&1 && printf '  %sok%s       docker daemon running\n' "$c_ok" "$c_off" \
    || { printf '  %sdown%s     docker daemon\n' "$c_err" "$c_off"; rc=1; }
  printf '\n%sOnly docker + compose + curl are needed to run the stack (~3 GB RAM, ~4.5 GB with Zabbix).\n' "$c_dim"
  printf 'promtool/amtool/prometheus/alertmanager come with the Prometheus & Alertmanager release tarballs (or brew install prometheus alertmanager).%s\n' "$c_off"
  return $rc
}

usage() {
  cat <<EOF
Observability Stack - run.sh

Usage: ./run.sh <command> [args]

Run the stack
  install-deps      install every dependency (../install.sh 04)
  doctor              check required tools
  start | up          metrics + logs + dashboards + alerting + demo app
  start-zabbix        same, plus Zabbix server/agent/web (UI on :8081)
  stop  | down        stop everything (data volumes kept)
  status | ps         container status
  logs [service]      follow logs
  urls                print the UI addresses
  reload              hot-reload Prometheus config and rules

Simulate incidents (see docs/RUNBOOKS.md)
  chaos errors [rate]   e.g. 0.3 = 30% of requests fail -> HighErrorRate
  chaos latency [ms]    e.g. 800 -> HighLatencyP95
  chaos down | up       stop/start the demo app -> ServiceDown
  chaos reset | status  clear chaos / show current mode

Zabbix
  zabbix-register     register the agent host + web check via the Zabbix API

Test
  validate            promtool, amtool, compose, yamllint, ruff
  test-rules          alert-rule unit tests (promtool)
  test                validate + rule tests + pytest
  test-live           live pipeline test with real binaries (~3.5 min, no Docker)

Clean up
  nuke                stop and DELETE all data volumes
EOF
}

cmd="${1:-help}"; shift || true
case "$cmd" in
  help|-h|--help) usage ;;
  install-deps)
    [[ -x ../install.sh ]] || die "../install.sh not found: it is in the full portfolio repo (git clone https://github.com/Mian-Basam/devops-portfolio)"
    exec ../install.sh 04 "$@" ;;
  doctor)        doctor ;;
  start|up)      need_docker; docker compose up -d --build; say "stack starting:"; urls ;;
  start-zabbix|up-zabbix)
    need_docker; docker compose --profile zabbix up -d --build; say "stack starting:"; urls
    echo "  Zabbix         http://localhost:8081   (Admin / zabbix)  - first start takes ~1 min"
    echo "  then run: ./run.sh zabbix-register" ;;
  stop|down)     need_docker; docker compose --profile zabbix down ;;
  status|ps)     need_docker; docker compose --profile zabbix ps ;;
  logs)          need_docker; docker compose logs -f --tail=50 "$@" ;;
  urls)          urls ;;
  reload)        need curl; curl -fsS -X POST localhost:9090/-/reload && say "Prometheus reloaded" ;;
  chaos)         need curl; ./scripts/chaos.sh "$@" ;;
  zabbix-register)
    need python3
    python3 zabbix/register_host.py --host lab-docker-host --dns zabbix-agent --web-url http://demo-app:8000/health ;;
  validate)
    need promtool amtool yamllint ruff docker
    promtool check rules prometheus/rules/*.yml
    amtool check-config alertmanager/alertmanager.yml
    docker compose --profile zabbix config -q
    yamllint -c .yamllint.yml .
    ruff check .
    say "all configs valid" ;;
  test-rules)    need promtool; promtool test rules prometheus/tests/alerts_test.yml ;;
  test)          "$0" validate && "$0" test-rules && python3 -m pytest -q ;;
  test-live)     need prometheus alertmanager python3 curl; ./scripts/live_pipeline_test.sh ;;
  nuke)
    need_docker
    read -r -p "This DELETES all metrics, logs, dashboards and Zabbix data. Type 'yes': " ans
    [[ "$ans" == "yes" ]] || die "aborted"
    docker compose --profile zabbix down -v ;;
  *)             usage; die "unknown command: $cmd" ;;
esac
