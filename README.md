# Observability Stack: Prometheus · Grafana · Loki · Alertmanager · Zabbix

[![CI](https://github.com/Mian-Basam/observability-stack/actions/workflows/ci.yml/badge.svg)](https://github.com/Mian-Basam/observability-stack/actions)
![Prometheus](https://img.shields.io/badge/Prometheus-2.54-E6522C?logo=prometheus&logoColor=white)
![Grafana](https://img.shields.io/badge/Grafana-11-F46800?logo=grafana&logoColor=white)
![Zabbix](https://img.shields.io/badge/Zabbix-7.0-D40000)
![Level](https://img.shields.io/badge/level-intermediate%20→%20advanced-orange)

> A complete, self-contained **monitoring, logging and alerting platform**
> that starts with one command, plus a demo service with **chaos
> endpoints** so you can trigger real incidents and watch the whole
> pipeline react.
>
> **Portfolio level 4 of 5**: monitoring, logging and alerting.

---

## Table of contents

1. [Introduction](#1-introduction)
2. [Purpose of the project](#2-purpose-of-the-project)
3. [Architecture](#3-architecture)
4. [What is monitored](#4-what-is-monitored)
5. [Tools and technologies](#5-tools-and-technologies)
6. [File structure](#6-file-structure)
7. [How to run: `run.sh`](#7-how-to-run-runsh)
8. [Quick start](#8-quick-start)
9. [Trigger an incident](#9-trigger-an-incident)
10. [Alerts](#10-alerts)
11. [Dashboards](#11-dashboards)
12. [Zabbix](#12-zabbix)
13. [Testing](#13-testing)
14. [Bugs found by the tests](#14-bugs-found-by-the-tests)
15. [Skills demonstrated](#15-skills-demonstrated)
16. [Further documentation](#16-further-documentation)

---

## 1. Introduction

This project runs a full observability platform in Docker Compose and
points it at a small **"orders" demo service**:

* **Metrics**: Prometheus scrapes the demo app, node-exporter (host),
  cAdvisor (containers) and the Blackbox exporter (HTTP/TCP/TLS probes).
* **Logs**: Promtail collects every container's logs and ships them to Loki.
* **Dashboards**: Grafana starts with three dashboards already provisioned as code.
* **Alerts**: 11 alert rules in Prometheus; Alertmanager groups, routes
  and de-duplicates them and sends them to a webhook receiver (which
  stands in for Slack, e-mail or PagerDuty).
* **Zabbix** (optional): agent-based infrastructure monitoring, with a
  script that registers hosts through the Zabbix API.

A built-in load generator keeps traffic flowing, and `./run.sh chaos ...`
injects errors, latency or downtime into the demo app so alerts actually
fire and resolve.

## 2. Purpose of the project

**Problem it solves.** Without monitoring you learn about outages from
your users. With bad monitoring you get flooded with noisy alerts and
ignore the important one. This project shows how to collect the right
signals, visualize them, and design alerts that page **one** person,
**once**, with a runbook link, when users are actually affected.

**Goals**

| Goal | How the project meets it |
|---|---|
| Collect metrics, logs and probes in one place | Prometheus, Loki and Blackbox, all queryable from Grafana |
| Alert on symptoms, not noise | RED metrics (Rate, Errors, Duration), `for:` durations, severities |
| Route alerts to the right team | Alertmanager routing tree: on-call vs payments team vs default |
| Avoid alert storms | Grouping and **inhibition** (ServiceDown suppresses the other alerts it causes) |
| Prove the alerting works | Promtool unit tests for every rule and a live end-to-end pipeline test |
| Practice incident response | Chaos endpoints + one runbook per alert |
| Cover both monitoring styles | Pull-based Prometheus and agent-based Zabbix side by side |

**Who it is for:** engineers learning Prometheus, Grafana and alert
design, and teams that want a reference stack to copy into their own
environment.

**Where it fits:** projects 1 to 3 built and ran systems; this project
watches them. The Ansible VMs from project 3 already run node_exporter and
can be added to `prometheus/prometheus.yml`, and project 5 reuses the same
Prometheus/Grafana approach for its API.

## 3. Architecture

```
   ┌──────────────┐  /metrics   ┌────────────┐  alerts   ┌──────────────┐  webhook  ┌────────────────┐
   │ demo-app     │────────────▶│ Prometheus │──────────▶│ Alertmanager │──────────▶│ webhook-logger │
   │ (orders API) │             │ rules, TSDB│           │ route/inhibit│           │ (Slack/e-mail  │
   └──────┬───────┘             └─────┬──────┘           └──────────────┘           │  in real life) │
          │ JSON logs                 │  ▲  ▲  ▲                                    └────────────────┘
          ▼                           │  │  │  └── blackbox-exporter (HTTP/TCP/TLS probes)
   ┌──────────────┐                   │  │  └───── cAdvisor (container CPU/mem)
   │ Promtail     │──push──▶ Loki     │  └──────── node-exporter (host CPU/mem/disk/net)
   └──────────────┘           │       │
                              ▼       ▼
                         ┌────────────────────┐
                         │ Grafana            │  3 provisioned dashboards
                         │ Prometheus + Loki  │  + Alertmanager datasource
                         └────────────────────┘

   Optional profile "zabbix":  Zabbix server ◀── Zabbix agent 2      Web UI :8081
                                    │
                               PostgreSQL
```

Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## 4. What is monitored

| Signal | Source | Examples |
|---|---|---|
| Service RED metrics | demo-app `/metrics` | request rate, **E**rror ratio, **D**uration p50/p95/p99 |
| Host | node-exporter | CPU, memory, disk (with 24h fill prediction), network, load |
| Containers | cAdvisor | per-container CPU, memory, restarts |
| Endpoints | Blackbox exporter | HTTP status, probe latency, TLS certificate expiry, TCP reachability |
| Logs | Promtail → Loki | all container logs; demo-app JSON fields parsed into labels |
| Infrastructure (agent-based) | Zabbix agent 2 | Linux template: CPU, memory, filesystems, processes; web scenario |

## 5. Tools and technologies

### Required to run

| Tool | Version | Used for | Install |
|---|---|---|---|
| Docker Engine / Docker Desktop | 24+ | running every component | [docs.docker.com](https://docs.docker.com/get-docker/) |
| Docker Compose plugin | v2 | starting the stack and the Zabbix profile | included with Docker Desktop |
| curl | any | chaos scenarios, Prometheus reload | preinstalled |
| Python 3 | 3.10+ | Zabbix host registration | python.org |

About **3 GB** free RAM (about **4.5 GB** with Zabbix). Ports 3000, 3100,
8000, 9090, 9093 and 9095 must be free (plus 8081 and 10051 with Zabbix).

### Required to develop and test

| Tool | Used for | Install |
|---|---|---|
| promtool | rule validation and alert unit tests | Prometheus release tarball / `brew install prometheus` |
| amtool | Alertmanager config validation | Alertmanager release tarball / `brew install alertmanager` |
| prometheus + alertmanager binaries | live pipeline test (`./run.sh test-live`) | same as above |
| pytest + flask, prometheus-client, gunicorn | Python tests | `pip install pytest flask prometheus-client gunicorn` |
| yamllint, ruff | YAML and Python lint | `pip install yamllint ruff` |

### Technology stack

| Category | Technologies |
|---|---|
| Metrics | Prometheus 2.54 (scraping, relabeling, recording rules, PromQL, `predict_linear`, histograms) |
| Exporters | node-exporter 1.8, cAdvisor 0.49, Blackbox exporter 0.25 |
| Alerting | Alertmanager 0.27 (routing, grouping, inhibition, webhooks) |
| Logging | Loki 3.2, Promtail 3.2, LogQL |
| Visualization | Grafana 11.2 (datasources and dashboards provisioned as code) |
| Infrastructure monitoring | Zabbix 7.0 (server, web, agent 2, JSON-RPC API), PostgreSQL 16 |
| Demo workload | Python 3.12, Flask, prometheus-client, Gunicorn |
| Orchestration | Docker Compose (profiles, healthchecks) |
| Quality / CI | promtool tests, amtool, pytest, ruff, yamllint, GitHub Actions |

## 6. File structure

```
04-observability-stack/
├── run.sh                             # ★ single entry point: ./run.sh help
├── docker-compose.yml                 # 11 services + 4 optional Zabbix services (profile "zabbix")
├── Makefile                           # make up | up-zabbix | test | test-live | ...
├── README.md                          # this document
├── .yamllint.yml                      # YAML lint rules
├── ruff.toml                          # Python lint rules
├── pytest.ini                         # pytest settings
│
├── demo-app/                          # the monitored "orders" service
│   ├── app.py                         #   /api/orders, /health, /metrics, /chaos/* endpoints, JSON logs
│   ├── Dockerfile                     #   1 worker + threads so chaos state is shared
│   ├── requirements.txt
│   └── tests/test_app.py              #   app + chaos endpoint tests
│
├── webhook-logger/                    # tiny Alertmanager receiver (stands in for Slack/e-mail)
│   ├── app.py                         #   prints each alert, keeps the last 100 at GET /alerts (:9095)
│   └── Dockerfile
│
├── prometheus/
│   ├── prometheus.yml                 # scrape jobs incl. blackbox relabeling
│   ├── rules/recording.yml            # RED recording rules (rate, error ratio, latency quantiles)
│   ├── rules/alerts.yml               # 11 alert rules (service, host, probes)
│   └── tests/alerts_test.yml          # promtool unit tests for the alerts
│
├── alertmanager/
│   └── alertmanager.yml               # routing tree, receivers, grouping, inhibition rules
│
├── blackbox/
│   └── blackbox.yml                   # probe modules: http_2xx (incl. TLS cert data), tcp_connect, icmp
│
├── loki/
│   └── loki.yml                       # log storage, 7-day retention
├── promtail/
│   └── promtail.yml                   # discovers containers via Docker API, parses JSON logs
│
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/datasources.yml  # Prometheus, Loki, Alertmanager
│   │   └── dashboards/dashboards.yml    # loads dashboards from grafana/dashboards
│   └── dashboards/
│       ├── service-red.json           # Service Overview (RED) + error logs
│       ├── host-overview.json         # CPU, memory, disk, network, containers
│       └── probes.json                # endpoint up/down, latency, TLS expiry
│
├── zabbix/
│   ├── register_host.py               # creates host, links Linux template, adds web scenario via API
│   └── tests/test_register_host.py    # runs against a fake JSON-RPC API
│
├── scripts/
│   ├── chaos.sh                       # errors | latency | down | up | reset | status
│   └── live_pipeline_test.sh          # real Prometheus + Alertmanager end-to-end test (no Docker)
│
├── docs/
│   ├── ARCHITECTURE.md                # components, ports, data flow, retention, scaling
│   ├── ALERTING.md                    # alert design, routing tree, inhibition, testing
│   ├── RUNBOOKS.md                    # one runbook per alert
│   ├── LOGGING.md                     # Loki/Promtail pipeline and LogQL queries
│   └── ZABBIX.md                      # setup, agents on VMs, API automation, Prometheus vs Zabbix
│
└── .github/workflows/ci.yml           # validate, rule tests, pytest, live pipeline, full stack check
```

## 7. How to run: `run.sh`

`run.sh` is the single entry point for this project and does not need
`make`. It checks that Docker is running before starting anything.

| Command | What it does |
|---|---|
| `./run.sh help` | List all commands |
| `./run.sh doctor` | Check Docker and the validation tools |
| `./run.sh start` | Start metrics + logs + dashboards + alerting + demo app; prints the URLs |
| `./run.sh start-zabbix` | Same, plus Zabbix (UI on :8081) |
| `./run.sh status` | Container status |
| `./run.sh logs [service]` | Follow logs |
| `./run.sh urls` | Print the UI addresses |
| `./run.sh reload` | Hot-reload Prometheus config and rules |
| `./run.sh chaos errors [rate]` | Make a share of requests fail (default 0.3) |
| `./run.sh chaos latency [ms]` | Add latency (default 800 ms) |
| `./run.sh chaos down` / `up` | Stop / start the demo app |
| `./run.sh chaos reset` / `status` | Clear chaos / show the current mode |
| `./run.sh zabbix-register` | Register the agent host and web check via the Zabbix API |
| `./run.sh validate` | promtool, amtool, Compose, yamllint, ruff |
| `./run.sh test-rules` | Alert unit tests |
| `./run.sh test` | validate + rule tests + pytest |
| `./run.sh test-live` | Live pipeline test with real binaries (~3.5 min) |
| `./run.sh stop` | Stop everything (data kept) |
| `./run.sh nuke` | Stop and **delete** all data volumes (asks to confirm) |

From the portfolio root you can also run `./run.sh 04 <command>`.

## 8. Quick start

```bash
git clone https://github.com/Mian-Basam/observability-stack.git
cd observability-stack

./run.sh doctor     # 1. check Docker is installed and running
./run.sh start      # 2. start the stack (or: ./run.sh start-zabbix)
```

| UI | URL | Login |
|---|---|---|
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | – |
| Alertmanager | http://localhost:9093 | – |
| Alert receiver (JSON) | http://localhost:9095 | – |
| Demo app | http://localhost:8000 | – |
| Zabbix | http://localhost:8081 | Admin / zabbix |

A load generator starts automatically, so the dashboards fill with data right away.

## 9. Trigger an incident

```bash
./run.sh chaos errors 0.3    # 30% of requests fail
# ~3 min later: HighErrorRate fires → routed to "oncall"
./run.sh chaos status

./run.sh chaos down          # stop the service
# ~1 min later: ServiceDown fires; HighErrorRate is *suppressed* (inhibition)

./run.sh chaos up && ./run.sh chaos reset   # recover → RESOLVED notifications
./run.sh chaos latency 800   # p95 > 500ms → HighLatencyP95 (warning, payments team)
```

The Grafana **Service Overview** dashboard shows the error ratio and
latency spike, and the error log lines from Loki appear in the same view.

## 10. Alerts

| Alert | Condition | For | Severity → receiver |
|---|---|---|---|
| ServiceDown | `up == 0` | 1m | critical → oncall |
| HighErrorRate | 5xx ratio > 5% | 2m | critical → oncall |
| HighLatencyP95 | p95 > 500ms | 5m | warning → payments-team |
| HostHighCpu | CPU > 85% | 10m | warning → default |
| HostLowMemory | available < 10% | 5m | warning → default |
| HostDiskWillFillIn24h | `predict_linear` < 0 and < 25% free | 30m | warning → default |
| HostDiskAlmostFull | < 10% free | 5m | critical → oncall |
| EndpointDown | `probe_success == 0` | 2m | critical → oncall |
| TlsCertExpiringSoon | cert expires < 14 days | 1h | warning → default |
| ContainerRestarting | > 2 restarts in 15m | – | warning → default |
| Watchdog | always firing | – | heartbeat (proves the pipeline works) |

**Inhibition:** ServiceDown suppresses other payments-team alerts, and
HostDiskAlmostFull suppresses HostDiskWillFillIn24h on the same mount.
On-call gets one page per incident instead of five.

Every alert links to a runbook: [docs/RUNBOOKS.md](docs/RUNBOOKS.md).
Design notes: [docs/ALERTING.md](docs/ALERTING.md).

## 11. Dashboards

Provisioned automatically from `grafana/dashboards/` as code:

| Dashboard | Panels |
|---|---|
| **Service Overview (RED)** (home) | req/s, error ratio and p95 stats with thresholds; requests by status; p50/p95/p99; chaos modes; orders/min; **error logs from Loki** |
| **Host Overview** | CPU %, memory %, disk free %, network throughput, load average, container memory |
| **Endpoint Probes** | probe up/down, probe duration, TLS days left, HTTP status codes |

## 12. Zabbix

```bash
./run.sh start-zabbix       # first start takes ~1 min while Zabbix creates its schema
./run.sh zabbix-register    # creates the host via the Zabbix API, links the Linux template,
                            # adds a web scenario for the demo app health URL
```

`zabbix/register_host.py` uses the Zabbix JSON-RPC API, so new servers
can be onboarded from a script or a CI pipeline instead of clicking
through the UI. Read [docs/ZABBIX.md](docs/ZABBIX.md) for agent
installation on VMs and a Prometheus vs Zabbix comparison.

## 13. Testing

| Test | Command | What it proves |
|---|---|---|
| Config validation | `./run.sh validate` | promtool, amtool, Compose, yamllint, ruff all pass |
| **Alert unit tests** | `./run.sh test-rules` | Alerts fire at the right threshold and **not before** their `for:` duration, with the right labels and annotations |
| Python tests | `pytest` (9) | Demo app + chaos endpoints; Zabbix script against a fake JSON-RPC API |
| **Live pipeline** | `./run.sh test-live` | Real Prometheus + Alertmanager binaries: scrape → recording rule → alert → routing → **inhibition** → webhook |

```
$ ./run.sh test-live
PASS  Prometheus scrapes the demo app
PASS  recording rule error ratio = 0.276 (> 0.05)
PASS  Watchdog delivered to heartbeat receiver
PASS  ServiceDown paged on-call
PASS  HighErrorRate inhibited while the service is down
```

CI runs all of the above, then starts the full Compose stack and checks
that every scrape target is `up` and the dashboards were provisioned.

## 14. Bugs found by the tests

| Bug | How it was found | Fix |
|---|---|---|
| The inhibit rule used `equal: [job]`, but HighErrorRate comes from a recording rule aggregated `by (service)`, which **drops the `job` label**. Inhibition could never match, so on-call would have been paged twice per outage. | Live pipeline test: Alertmanager showed HighErrorRate `active` while ServiceDown was firing | `equal: [team]` plus an explicit `alertname!="ServiceDown"` target matcher; asserted in `test-live` |

## 15. Skills demonstrated

Prometheus (scraping, relabeling, recording rules, PromQL, `predict_linear`,
histograms) · alert design and **unit-testing alerts** · Alertmanager
routing, grouping and inhibition · Grafana provisioning (dashboards as
code) · centralized logging with Loki/Promtail and LogQL · blackbox and TLS
monitoring · **Zabbix** server/agent and API automation · Docker Compose ·
incident simulation and runbooks.

## 16. Further documentation

| Document | Contents |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, ports, data flow, retention, scaling notes |
| [docs/ALERTING.md](docs/ALERTING.md) | How alerts are designed: symptoms vs causes, `for:`, severities, routing tree, inhibition, testing |
| [docs/RUNBOOKS.md](docs/RUNBOOKS.md) | One runbook per alert: meaning, impact, diagnosis, fix |
| [docs/LOGGING.md](docs/LOGGING.md) | Loki/Promtail pipeline and useful LogQL queries |
| [docs/ZABBIX.md](docs/ZABBIX.md) | Setup, agent on VMs, templates, API automation, Prometheus vs Zabbix |

---

**Author:** Basil Ahtisham · [LinkedIn](https://linkedin.com/in/mianbasil) · [GitHub](https://github.com/Mian-Basam)
