.PHONY: help up up-zabbix down nuke ps logs validate test-rules test test-live zabbix-register reload
help:            ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'
up:              ## start metrics + logs + dashboards stack
	docker compose up -d --build
	@echo "Grafana http://localhost:3000 (admin/admin) | Prometheus :9090 | Alertmanager :9093"
up-zabbix:       ## also start Zabbix (web UI on :8081, Admin/zabbix)
	docker compose --profile zabbix up -d --build
down:            ## stop everything (keep data)
	docker compose --profile zabbix down
nuke:            ## stop and delete all data volumes
	docker compose --profile zabbix down -v
ps:              ## container status
	docker compose --profile zabbix ps
logs:            ## follow logs
	docker compose logs -f --tail=50
reload:          ## hot-reload Prometheus config/rules
	curl -X POST localhost:9090/-/reload
validate:        ## static validation of every config
	promtool check rules prometheus/rules/*.yml
	amtool check-config alertmanager/alertmanager.yml
	docker compose --profile zabbix config -q
	yamllint -c .yamllint.yml .
	ruff check .
test-rules:      ## alert rule unit tests
	promtool test rules prometheus/tests/alerts_test.yml
test:            ## validate + rule tests + python tests
	$(MAKE) validate test-rules
	python3 -m pytest -q
test-live:       ## live pipeline test with real binaries (~3.5 min, no Docker)
	./scripts/live_pipeline_test.sh
zabbix-register: ## register the agent host + web check in Zabbix
	python3 zabbix/register_host.py --host lab-docker-host --dns zabbix-agent --web-url http://demo-app:8000/health
