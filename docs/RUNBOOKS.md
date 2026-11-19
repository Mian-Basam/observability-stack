# Runbooks

Each section answers: what it means, the impact, how to diagnose, and how to fix.

## ServiceDown

**Meaning:** Prometheus cannot scrape the service for 1 minute.
**Impact:** the service is probably unavailable to users.

1. `docker compose ps demo-app`: is it running, restarting, or unhealthy?
2. `docker compose logs --tail=100 demo-app`: look for crash traces.
3. `curl -v localhost:8000/health`: does it answer at all?
4. If the process is up but not scrapable, check the Prometheus Targets page for the scrape error (DNS, timeout, wrong port).

**Fix:** restart (`docker compose restart demo-app`); if a deploy caused it, roll back.

## HighErrorRate

**Meaning:** more than 5% of requests return 5xx for 2 minutes.

1. Grafana → Service Overview: which route, and since when?
2. Loki: `{service="demo-app", level="ERROR"} | json` and read the `msg` and route.
3. Did a deploy or config change happen at that time?
4. Lab: `./scripts/chaos.sh status`. Is chaos mode active?

**Fix:** roll back a bad deploy; fix or fail over the failing dependency; `./scripts/chaos.sh reset` in the lab.

## HighLatencyP95

**Meaning:** the slowest 5% of requests take more than 500ms, for 5 minutes.

1. Is it all routes or one? (Latency percentiles panel)
2. Saturation: CPU throttling of the container (`container_cpu_cfs_throttled_seconds_total`), host load.
3. Downstream dependency slow (database, external API)?

**Fix:** scale out, remove the slow dependency from the hot path, or raise resource limits.

## HostHighCpu

1. `top` / `ps -eo pid,comm,%cpu --sort=-%cpu | head` on the host.
2. Container view: Host Overview → container memory/CPU, or `docker stats`.
3. Expected (batch job) or unexpected (runaway process, crypto-miner)?

## HostLowMemory

1. `free -h`, `ps -eo pid,comm,rss --sort=-rss | head`.
2. `dmesg -T | grep -i oom`: has the OOM killer acted already?
3. Look for a memory leak: steadily growing container memory in Grafana.

## HostDiskWillFillIn24h / HostDiskAlmostFull

1. `df -h` and `df -i`.
2. `sudo du -xh --max-depth=1 /var | sort -h`.
3. Usual suspects: Docker images/volumes (`docker system df`), logs, old backups, deleted-but-open files (`lsof +L1`).

**Fix:** `docker system prune`, rotate or compress logs, move backups off-host, extend the volume.

## EndpointDown

1. Prometheus → `probe_http_status_code{instance="..."}` and `probe_duration_seconds`.
2. Reproduce from the blackbox container: `docker compose exec blackbox wget -S -O- <url>`.
3. Layered check: DNS → TCP → TLS → HTTP (see Project 1 `netcheck.sh`).

## TlsCertExpiringSoon

1. `echo | openssl s_client -connect host:443 -servername host 2>/dev/null | openssl x509 -noout -dates`
2. Renew (certbot / internal CA) and reload the web server.
3. Check that automatic renewal is scheduled and working.

## ContainerRestarting

1. `docker compose ps`: restart count; `docker inspect <c> --format '{{.State.OOMKilled}} {{.State.ExitCode}}'`.
2. Exit code 137 means it was OOM-killed (raise the memory limit or fix the leak); a non-zero exit is an app crash, so read the logs.

## Watchdog stopped arriving

The **monitoring itself** is broken. Check in order: Prometheus up? Alertmanager up? Receiver reachable? `docker compose ps`.
