# Zabbix

## Start

```bash
make up-zabbix
# wait ~60s for the schema to be created on first start
open http://localhost:8081      # Admin / zabbix  (change it!)
make zabbix-register
```

`zabbix-agent` runs with `ZBX_HOSTNAME=lab-docker-host`.
`register_host.py` creates a host with that exact name, links
**Linux by Zabbix agent**, and adds a web scenario for
`http://demo-app:8000/health`. Data appears under *Monitoring → Latest data*
within a few minutes.

## Components

| Component | Role |
|---|---|
| Zabbix server | Polls agents, evaluates triggers, sends notifications |
| Database (PostgreSQL) | Configuration and history |
| Web frontend | UI and JSON-RPC API |
| Agent 2 | Runs on monitored hosts; passive checks (server polls :10050) and active checks (agent pushes to :10051) |

## Monitoring a VM (e.g. Project 3 servers)

```bash
sudo apt-get install -y zabbix-agent2
sudo sed -i 's/^Server=.*/Server=<zabbix-server-ip>/; s/^ServerActive=.*/ServerActive=<zabbix-server-ip>/; s/^Hostname=.*/Hostname=web01/' /etc/zabbix/zabbix_agent2.conf
sudo systemctl enable --now zabbix-agent2
sudo ufw allow from <zabbix-server-ip> to any port 10050 proto tcp
python3 zabbix/register_host.py --url http://<zabbix-web>:8081 --host web01 --ip 192.168.56.11
```

This is easy to turn into an Ansible role in Project 3.

## Key concepts

| Concept | Meaning |
|---|---|
| Host | A monitored device |
| Item | One value collected, e.g. `system.cpu.util` |
| Trigger | Expression on items that creates a problem, e.g. `last(/web01/vfs.fs.size[/,pused])>90` |
| Template | Reusable set of items, triggers and graphs, linked to many hosts |
| Action | What to do on a problem: notify, run a script |
| Web scenario | Synthetic HTTP check with steps |
| Discovery (LLD) | Automatically create items for filesystems, interfaces, etc. |

## API automation

The JSON-RPC API (`/api_jsonrpc.php`) allows everything the UI does.
`register_host.py` shows the pattern: `user.login` → bearer token →
`hostgroup.get/create` → `template.get` → `host.create/update` →
`httptest.create`. It is idempotent: re-running updates instead of
duplicating. Its tests run it against a fake API server.

## Prometheus vs Zabbix

| | Prometheus | Zabbix |
|---|---|---|
| Model | Pull over HTTP, exporters | Agent (passive/active), SNMP, IPMI, HTTP |
| Configuration | YAML in git | Mostly UI/DB; API and template export for automation |
| Data model | Labeled time series, PromQL | Hosts → items → triggers |
| Strengths | Cloud-native, containers, Kubernetes, ad-hoc querying | Traditional data centers, network devices (SNMP), Windows, built-in UI, inventory and maps |
| Alerting | Alertmanager | Built-in actions and escalations |
| Storage | Local TSDB (+ remote write) | SQL database |

Many on-premises environments run **both**: Zabbix for servers, network
gear and hardware, and Prometheus for applications and containers. Grafana
can show both side by side (the Zabbix datasource plugin).
