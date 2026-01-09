# Application Insights Monitoring Guide

This repository now ships with Application Insights telemetry for both traces and custom metrics.
Use the snippets below to quickly build a dashboard in Azure and wire up alerting.

## What is collected

- **Request Count / Error Rate / Latency**: Captured automatically via OpenCensus middleware.
- **Custom Refresh Metric**: Every call to `POST /api/v1/scraper/refresh` emits a `refresh_invocations` metric with `refresh_status` dimension (`success`/`failed`).
- **Structured Logs**: JSON-style request logs are forwarded to Application Insights for deeper investigation (searchable via `traces`).

## Kusto (KQL) snippets for dashboards

Create a Workbook in the Application Insights resource and add the following queries as visuals:

### Requests per endpoint
```kusto
requests
| summarize count() by name, resultCode
| sort by count_ desc
```

### Average response time (ms)
```kusto
requests
| summarize avg(duration) by name
| sort by avg_duration desc
```

### Error rate
```kusto
let total = toscalar(requests | summarize count());
requests
| where success == false
| summarize errors = count() by bin(timestamp, 5m)
| extend errorRate = round(100.0 * errors / total, 2)
```

### Refresh execution frequency
```kusto
customMetrics
| where name == "refresh_count"
| summarize refreshes = sum(value) by tostring(customDimensions.refresh_status), bin(timestamp, 15m)
```

Add charts for each query to produce a single “Operations Overview” workbook. Pin it to the dashboard for quick access.

## Optional alert rule example

Create an alert on the Application Insights resource with:

- **Signal type**: Custom log search
- **Query**:
  ```kusto
  requests
  | where success == false
  | summarize errors = count() by bin(timestamp, 5m)
  | where errors > 0
  ```
- **Threshold**: Greater than 0
- **Frequency**: 5 minutes

This yields a simple error-rate alert (adjust severity/threshold as needed).

## Configuration notes

- Set `APPLICATIONINSIGHTS_CONNECTION_STRING` (or legacy `APPINSIGHTS_INSTRUMENTATIONKEY`) in your deployment environment.
- Telemetry exporters initialize automatically at startup; no code changes are required per environment.
