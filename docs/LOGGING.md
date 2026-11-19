# Centralized Logging with Loki

## Pipeline

```
container stdout/stderr → Docker json-file log → Promtail (docker_sd) → Loki → Grafana Explore
```

* Promtail discovers containers through the Docker socket, restricted to
  this Compose project with a label filter.
* Labels attached: `service` (compose service name) and `container`.
* For `demo-app`, a pipeline stage parses JSON and promotes `level` and
  `route` to labels.

Keep labels low-cardinality (service, level, route). **Never** use request
IDs or user IDs as labels: they create one stream per value and slow Loki
down. Filter them at query time instead.

## Docker log rotation

Every service uses:

```yaml
logging: { driver: json-file, options: { max-size: "10m", max-file: "3" } }
```

so container logs cannot fill the host disk.

## LogQL examples (Grafana → Explore → Loki)

```logql
# all errors from the demo service
{service="demo-app", level="ERROR"}

# parse JSON and filter on a field
{service="demo-app"} | json | status >= 500

# slow requests
{service="demo-app"} | json | duration_ms > 500

# error lines per minute, per route (a metric from logs)
sum by (route) (count_over_time({service="demo-app", level="ERROR"}[1m]))

# anything mentioning "timeout" across all containers
{service=~".+"} |= "timeout"
```

## Metrics vs logs

Use **metrics** to detect (cheap, aggregated, alertable) and **logs** to
explain (the details of the specific failing requests). The Service
Overview dashboard puts both side by side.
