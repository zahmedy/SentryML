# SentryML API

Base URL: your API host (for local dev: `http://localhost:8000`).

All endpoints below require an API key header:

```
X-API-Key: sk_live_...
```

## POST /v1/events/prediction
Ingest a prediction event. If the model is new, it is registered automatically.

Notes:
- `event_time` is clamped to "now" if it is in the future.
- `score` is required and enables drift monitoring.

Request body

```json
{
  "model_id": "fraud_v1",
  "entity_id": "user_123",
  "prediction": "approve",
  "score": 0.87,
  "event_time": "2026-01-16T12:00:00Z"
}
```

Response 200

```json
{
  "event_id": "9b7e7c2c-2a8a-4c0f-9b5d-7f1bdb9a4f9c",
  "org_id": "5f6d11bb-5f8b-4c7f-9d3b-98f83f5fd9c9",
  "model_id": "fraud_v1",
  "entity_id": "user_123",
  "score": 0.87,
  "prediction": "approve",
  "event_time": "2026-01-16T12:00:00Z",
  "ingested_at": "2026-02-03T18:42:12.123Z"
}
```

## GET /v1/models
List models observed for the authenticated org.

Response 200

```json
[
  {
    "model_id": "fraud_v1",
    "event_count": 1287,
    "first_seen_at": "2026-01-10T05:12:00Z",
    "last_seen_at": "2026-02-03T18:41:10Z",
    "is_enabled": false,
    "baseline_days": 14,
    "current_days": 7,
    "num_bins": 10,
    "min_samples": 500,
    "warn_threshold": 0.1,
    "critical_threshold": 0.2,
    "status": "ok"
  }
]
```

## GET /v1/models/{model_id}/drift
Fetch drift history for a model.

Query params
- `limit` (int, default 50): number of drift records to return

Response 200

```json
[
  {
    "drift_id": "0e83c6d7-38fe-4fa0-9442-33a4d2a2f03a",
    "org_id": "5f6d11bb-5f8b-4c7f-9d3b-98f83f5fd9c9",
    "model_id": "fraud_v1",
    "computed_at": "2026-02-03T18:30:00Z",
    "baseline_start": "2026-01-20T00:00:00Z",
    "baseline_end": "2026-02-02T23:59:59Z",
    "current_start": "2026-02-03T00:00:00Z",
    "current_end": "2026-02-03T18:00:00Z",
    "psi_score": 0.14,
    "baseline_n": 4200,
    "current_n": 380
  }
]
```

## GET /v1/incidents
List incidents for the authenticated org.

Query params
- `status` (string, default `open`): `open`, `closed`, or `any`
- `limit` (int, default 50)

Response 200

```json
[
  {
    "incident_id": "7b2c9f8a-0f54-4d1a-bd30-f0f9c1d7c5b1",
    "org_id": "5f6d11bb-5f8b-4c7f-9d3b-98f83f5fd9c9",
    "model_id": "fraud_v1",
    "metric": "psi_score",
    "state": "open",
    "severity": "WARN",
    "acknowledged_by_user_id": null,
    "value": 0.16,
    "opened_at": "2026-02-03T18:30:00Z",
    "acknowledged_at": null,
    "resolved_at": null,
    "closed_at": null,
    "drift_id": "0e83c6d7-38fe-4fa0-9442-33a4d2a2f03a"
  }
]
```

## Errors

All endpoints:
- `401 Unauthorized`: missing or invalid `X-API-Key`

