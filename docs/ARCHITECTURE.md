# Architecture

## Components and ports

| Service | Image | Port | Role |
|---|---|---|---|
| demo-app | built from `demo-app/` | 8000 | Instrumented "orders" service with chaos endpoints |
| load-generator | curlimages/curl | – | Continuous traffic (~6 req/s) |
| prometheus | prom/prometheus:v2.54.1 | 9090 | Scrapes metrics, evaluates rules, stores TSDB (7d) |
| alertmanager | prom/alertmanager:v0.27.0 | 9093 | Groups, routes, inhibits and sends alerts |
| webhook-logger | built from `webhook-logger/` | 9095 | Alert receiver standing in for Slack/e-mail |
| node-exporter | prom/node-exporter:v1.8.2 | 9100 (internal) | Host metrics |
| cadvisor | gcr.io/cadvisor/cadvisor:v0.49.1 | 8080 (internal) | Container metrics |
| blackbox | prom/blackbox-exporter:v0.25.0 | 9115 (internal) | Synthetic HTTP/TCP probes |
| loki | grafana/loki:3.2.0 | 3100 | Log storage (7d retention) |
| promtail | grafana/promtail:3.2.0 | – | Discovers containers via Docker API, ships logs |
| grafana | grafana/grafana:11.2.0 | 3000 | Dashboards; Prometheus, Loki, Alertmanager datasources |
| zabbix-db / -server / -web / -agent | zabbix 7.0, postgres 16 | 10051, 8081 | Optional profile `zabbix` |

## Data flows

**Metrics (pull):** Prometheus scrapes each target every 15s over HTTP.
Exporters translate system state into the Prometheus text format.

**Blackbox (pull via proxy):** Prometheus asks
`blackbox:9115/probe?target=<url>&module=http_2xx`. The relabeling in
`prometheus.yml` turns the target list into those parameters while
keeping the original URL as the `instance` label.

**Rules:** recording rules pre-compute expensive expressions (request
rate, error ratio, p95) every 15s. Alerts and dashboards reuse them, so
the PromQL stays consistent and cheap.

**Alerts (push):** Prometheus sends firing and resolved alerts to
Alertmanager, which deduplicates, groups (`alertname, service, instance`),
applies inhibition, and sends one notification per group to a receiver.

**Logs (push):** Promtail tails the Docker JSON log files of containers
in this Compose project and pushes them to Loki with `service` and
`container` labels. demo-app logs are JSON, so `level` and `route` become
labels and can be filtered efficiently.

## Retention and storage

| Data | Where | Retention |
|---|---|---|
| Metrics | volume `prometheus-data` | 7 days (`--storage.tsdb.retention.time`) |
| Logs | volume `loki-data` | 7 days (`limits_config.retention_period`) |
| Dashboards | git (`grafana/dashboards`) | versioned |
| Zabbix history | volume `zabbix-db` | Zabbix housekeeper defaults |

## Monitoring other machines

* **VMs from Project 3:** add `192.168.56.11:9100` (etc.) to the `node` job.
  The node_exporter role there already exposes port 9100 to the monitoring network.
* **Zabbix:** install `zabbix-agent2` on the VM with `Server=<zabbix-server-ip>`,
  then `python3 zabbix/register_host.py --host web01 --ip 192.168.56.11`.

## Scaling notes (beyond this lab)

* Prometheus is a single node: use federation or remote-write (Thanos, Mimir) for long-term or HA storage.
* Run Alertmanager as a 3-node cluster (gossip) for HA.
* Run Loki in microservices mode with object storage for large log volumes.
