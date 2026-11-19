# Alerting Design

## Principles used here

1. **Alert on symptoms users feel, not every cause.** The pages are
   ServiceDown, HighErrorRate and EndpointDown. CPU and memory are
   warnings, because high CPU is only a problem if users notice it.
2. **Every page must be actionable** and link to a runbook (`runbook_url`).
3. **Use `for:` to avoid flapping.** A single bad scrape should not wake anyone.
4. **Predict instead of react where possible.** `HostDiskWillFillIn24h`
   uses `predict_linear` over 6h, giving a day of warning instead of an outage.
5. **One incident, one page.** Inhibition rules suppress downstream noise.
6. **Test the alerting itself.** The Watchdog alert is always firing; if
   the heartbeat stops arriving, the monitoring is broken.

## Severities

| Severity | Meaning | Delivery | Repeat |
|---|---|---|---|
| critical | Users affected now, or will be very soon | oncall (page) | 1h |
| warning | Needs attention during working hours | team channel / default | 4h |
| none | Meta (Watchdog) | heartbeat | 5m |

## Routing tree

```
route (default receiver: default, group_by: alertname, service, instance)
├── alertname="Watchdog"   → heartbeat
├── severity="critical"    → oncall
└── team="payments"        → payments-team
```

The first matching route wins (no `continue: true`). Check it with:

```bash
amtool config routes test --config.file=alertmanager/alertmanager.yml severity=critical team=payments
# oncall
```

## Grouping and timing

| Setting | Value | Effect |
|---|---|---|
| `group_wait` | 30s | Wait for related alerts before the first notification |
| `group_interval` | 5m | Minimum gap between updates for the same group |
| `repeat_interval` | 4h (1h critical) | Re-notify if still firing |

## Inhibition

```yaml
- source_matchers: [alertname="ServiceDown"]
  target_matchers: [team="payments", alertname!="ServiceDown"]
  equal: [team]
```

When the service is down, its error-rate and latency alerts are
meaningless, so they are suppressed. The labels in `equal:` must exist on
**both** alerts. The original version used `job`, which the recording
rules aggregate away, so it never matched. The live pipeline test caught it.

## Testing alerts

* `promtool test rules prometheus/tests/alerts_test.yml` feeds synthetic
  time series and asserts exactly when each alert fires, with which labels
  and annotations. It covers the `for:` delay, thresholds (20% fires,
  1% does not), recording rule math, disk and probe alerts.
* `scripts/live_pipeline_test.sh` runs the real binaries end to end.

## Silencing during maintenance

```bash
amtool silence add --alertmanager.url=http://localhost:9093 \
  alertname=ServiceDown --duration=30m --comment="planned deploy" --author=basil
amtool silence query --alertmanager.url=http://localhost:9093
```
