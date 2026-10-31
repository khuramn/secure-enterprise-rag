# Monitoring and Security Audit Logging

## Purpose

Milestone 16 introduces Azure-based observability and centralised security audit logging for the Secure Enterprise RAG application.

The design aims to provide request correlation, security event visibility, data minimisation and a local audit trail.

## Azure monitoring architecture

- Azure Application Insights collects application request telemetry and selected security audit events.
- Azure Log Analytics provides the workspace for querying telemetry.
- Azure Monitor OpenTelemetry instruments the FastAPI application.
- A separate JSONL audit log maintains a local record.

Terraform resources:
- `azurerm_log_analytics_workspace.rag`
- `azurerm_application_insights.rag`

Development configuration:
- Region: UK South
- Retention: 30 days
- Log Analytics daily quota: 0.5 GB

## Telemetry configuration

The application reads `APPLICATIONINSIGHTS_CONNECTION_STRING` from its environment.

The OpenTelemetry service name is `secure-enterprise-rag-api`, with environment `dev`.

Live metrics, performance counters, offline telemetry storage and automatic HTTP client instrumentation are disabled.

FastAPI instrumentation is enabled explicitly. Request and response header capture is disabled.

## Security audit events

The audit logger validates event data before writing structured JSON records.

The implementation supports:
- Local JSONL audit logging
- Forwarding validated, pseudonymised audit events to Azure
- Authentication and authorisation failure auditing
- Retrieval and response event auditing
- Request ID correlation

Raw identity information should not be included in exported audit events.

The application must not log bearer tokens, API keys, connection strings, document contents or user prompts.

## Request correlation

The API generates a UUID request ID.

The request ID is included in the API response as `X-Request-ID` and added to the active OpenTelemetry span as `rag.request_id`.

This allows application requests and security audit events to be investigated together.

## Example KQL queries

### Recent API requests

```kusto
AppRequests
| where TimeGenerated > ago(24h)
| order by TimeGenerated desc
| take 50
```

### Security audit traces

```kusto
AppTraces
| where TimeGenerated > ago(24h)
| where Message has "api.authentication.denied"
| order by TimeGenerated desc
| take 50
```

### Search for a specific request ID

Replace the placeholder with an actual request ID:

```kusto
union AppRequests, AppTraces
| where TimeGenerated > ago(24h)
| where tostring(Properties) has "<REQUEST_ID>"
    or Message has "<REQUEST_ID>"
| order by TimeGenerated asc
```

## Verification evidence

Milestone 16 validation included:

- Application Insights receiving security audit traces
- API request telemetry appearing in Azure
- Request ID correlation between request and audit records
- Local audit logging when the Application Insights connection string is absent
- 22 passing application regression tests
- Terraform formatting and validation checks

## Operational limitations

- Disabling offline telemetry storage means failed exports may result in missing Azure telemetry.
- Local audit logging is not equivalent to a durable, centralised delivery queue.
- The 0.5 GB daily ingestion quota may cause telemetry loss when reached.
- The 30-day retention setting is a development baseline, not a production retention policy.
- The HMAC pseudonymisation key must be managed as a stable secret for consistent pseudonyms across restarts.
- Azure Monitor exporter failures may not always be visible to the application.
- The implementation has not been validated against every production outage or failure scenario.

## Future production hardening

- Manage secrets through Azure Key Vault or an approved secret-management mechanism.
- Restrict monitoring resource access using least-privilege RBAC.
- Define alerting for authentication failures, abnormal access patterns and telemetry health.
- Establish production retention and ingestion requirements.
- Review network access and private connectivity.
- Evaluate tamper-resistant, durable security audit storage.
- Incorporate monitoring threats and residual risks into the Milestone 17 threat model.
