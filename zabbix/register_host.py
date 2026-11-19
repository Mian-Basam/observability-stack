#!/usr/bin/env python3
"""Register a host in Zabbix via its JSON-RPC API (Zabbix 7.0).

Creates (or updates) a host with an agent interface, links the
"Linux by Zabbix agent" template, and optionally adds an HTTP web scenario.

  python3 zabbix/register_host.py --host lab-docker-host --dns zabbix-agent \\
      --web-url http://demo-app:8000/health

Defaults match `docker compose --profile zabbix` (Admin / zabbix on :8081).
"""
import argparse
import json
import sys
import urllib.request


class Zabbix:
    def __init__(self, url, user, password):
        self.url = url.rstrip("/") + "/api_jsonrpc.php"
        self.token = None
        self._id = 0
        self.token = self.call("user.login", {"username": user, "password": password})

    def call(self, method, params):
        self._id += 1
        body = {"jsonrpc": "2.0", "method": method, "params": params, "id": self._id}
        headers = {"Content-Type": "application/json-rpc"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.url, json.dumps(body).encode(), headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
        if "error" in data:
            raise RuntimeError(f"{method}: {data['error'].get('data') or data['error']}")
        return data["result"]


def ensure_group(zbx, name):
    found = zbx.call("hostgroup.get", {"filter": {"name": [name]}})
    return found[0]["groupid"] if found else zbx.call("hostgroup.create", {"name": name})["groupids"][0]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://localhost:8081")
    ap.add_argument("--user", default="Admin")
    ap.add_argument("--password", default="zabbix")
    ap.add_argument("--host", required=True, help="host name; must equal ZBX_HOSTNAME on the agent")
    ap.add_argument("--dns", help="agent DNS name")
    ap.add_argument("--ip", default="", help="agent IP (used when --dns is not given)")
    ap.add_argument("--group", default="Linux servers")
    ap.add_argument("--template", default="Linux by Zabbix agent")
    ap.add_argument("--web-url", help="optional URL to monitor with a web scenario")
    args = ap.parse_args()
    if not args.dns and not args.ip:
        ap.error("give --dns or --ip")

    zbx = Zabbix(args.url, args.user, args.password)
    group_id = ensure_group(zbx, args.group)
    templates = zbx.call("template.get", {"filter": {"host": [args.template]}})
    if not templates:
        sys.exit(f"template not found: {args.template}")
    template_ref = [{"templateid": templates[0]["templateid"]}]

    existing = zbx.call("host.get", {"filter": {"host": [args.host]}})
    if existing:
        host_id = existing[0]["hostid"]
        zbx.call("host.update", {"hostid": host_id, "groups": [{"groupid": group_id}], "templates": template_ref})
        print(f"updated host {args.host} ({host_id})")
    else:
        interface = {"type": 1, "main": 1, "useip": 0 if args.dns else 1,
                     "ip": args.ip, "dns": args.dns or "", "port": "10050"}
        host_id = zbx.call("host.create", {"host": args.host, "groups": [{"groupid": group_id}],
                                           "interfaces": [interface], "templates": template_ref})["hostids"][0]
        print(f"created host {args.host} ({host_id})")

    if args.web_url:
        name = f"Health {args.web_url}"
        if zbx.call("httptest.get", {"hostids": host_id, "filter": {"name": [name]}}):
            print("web scenario already present")
        else:
            zbx.call("httptest.create", {
                "name": name, "hostid": host_id, "delay": "30s",
                "steps": [{"name": "health", "url": args.web_url, "status_codes": "200", "no": 1}],
            })
            print(f"added web scenario for {args.web_url}")


if __name__ == "__main__":
    main()
