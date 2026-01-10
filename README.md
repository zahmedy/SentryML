# SentryML
SaaS that monitors ML decisions, detects drift, and alerts teams before business metrics degrade.

## Repo strcture

sentryml/
  apps/
    api/                 # FastAPI: ingest + query + admin
    worker/              # scheduled drift jobs + alerts
  packages/
    core/                # shared types + metrics (PSI) + config parsing
  infra/
    docker-compose.yml   # api + db + worker
  docs/
    architecture.md
    api.md


## Core components (minimal, shippable)

1) API service (FastAPI)

Endpoints:

POST /v1/events/prediction ✅ ingest prediction event
POST /v1/events/outcome ✅ ingest outcome event (optional)
GET /v1/models/{model_id}/drift ✅ last drift results
GET /v1/incidents ✅ list incidents
POST /v1/monitors ✅ create/update monitor config (baseline/current windows, thresholds)

2) Database (Postgres)

Tables (MVP):

prediction_events
outcome_events
monitor_configs
drift_results
incidents
alert_routes (optional: where to send alerts)

3) Worker

Runs every X minutes/hours
For each monitor config:
queries baseline/current windows
computes PSI on score distribution
writes drift_results
creates incidents + triggers alert if needed

4) Alerting (simple first)

Slack webhook OR email (pick one first)
Store last-alert time to avoid spam

## The universal event schema (what you ingest)

## Prediction event

Required:

event_id (UUID) (or server generates)
model_id
entity_id
timestamp
score (float)

Optional:

prediction (class/label)
features (json) — optional
segment (json) — like country/device/channel
latency_ms, request_id, model_version

## Outcome event

Required:

outcome_id (UUID)
entity_id
timestamp
value (bool/number)

Optional:

event_id (if client has it)
outcome_type (“label”, “conversion”, …)