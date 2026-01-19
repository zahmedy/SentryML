# SentryML

SentryML monitors machine learning models in production for **data drift** and turns distribution changes into **clear, actionable incidents**.

It is designed to be simple, explicit, and production-oriented.

---

## Why SentryML exists

Machine learning models often fail silently in production when incoming data changes.

These changes may come from:
- upstream pipeline updates
- changes in user behavior
- seasonal or regional effects
- logging or schema issues

Without monitoring, these shifts can go unnoticed until downstream metrics degrade.

SentryML detects **distribution drift early**, before those failures become costly.

---

## How SentryML works

### 1. Prediction ingestion
Your application sends prediction events to SentryML via an API.

A prediction event typically includes:
- `model_id`
- `prediction`
- optional `score` or confidence
- timestamp

You do **not** send training data, feature values, or model artifacts.

As soon as events are received, the model is automatically registered.

---

### 2. Baseline vs current comparison
For each monitored model, SentryML compares:
- a **baseline window** (historical data)
- a **current window** (recent data)

These windows are configurable per model.

---

### 3. Drift detection
SentryML computes a **Population Stability Index (PSI)** score to measure how much the data distribution has shifted.

PSI is used because it is:
- widely understood
- interpretable
- stable in production
- inexpensive to compute

Severity is determined by thresholds:
- **OK** — no meaningful shift
- **Warning** — moderate shift
- **Critical** — significant shift

---

### 4. Incidents
When drift crosses a threshold, SentryML opens an **incident**.

Each incident has:
- a **severity** (`warn` or `critical`)
- a **state** (`open`, `acknowledged`, `resolved`, `closed`)
- a clear timeline showing how it evolved

Incidents are meant to be understandable and auditable, not noisy.

---

### 5. Alerts
When incidents open, escalate, or resolve, SentryML sends alerts (e.g. Slack).

Alerts are designed to answer quickly:
- What happened?
- How serious is it?
- Why did it happen?
- What happens next?

Each alert links directly to the incident detail page.

---

### 6. Automatic resolution
SentryML continuously re-evaluates drift.

If the data returns to normal:
- the incident is **resolved automatically**
- a resolution alert is sent

No manual cleanup is required.

---

### 7. Investigation and acknowledgment
From the UI, you can:
- inspect incident timelines
- review recent prediction activity
- acknowledge incidents once reviewed
- manually close acknowledged incidents

Acknowledging an incident marks it as *seen*.  
It does **not** silence alerts.

---

## Monitoring model

- Monitoring is enabled per model
- Drift detection runs on a scheduled worker
- All state changes are visible and explicit
- No hidden automation

---

## What SentryML does not do

By design, SentryML does **not**:
- measure model accuracy
- require ground-truth labels
- inspect raw feature values
- store model artifacts or weights
- take automated corrective actions

SentryML focuses on **early, reliable signal**, not automated decisions.

---

## Data and privacy

SentryML stores only the data required for monitoring:
- prediction events (limited to fields you send)
- aggregated statistics for drift detection
- incident records and timelines
- basic model metadata

SentryML does **not** store:
- training data
- raw input payloads
- feature values
- labels
- model artifacts

API keys are hashed and never stored in plaintext.

---

## Who SentryML is for

SentryML is built for:
- ML engineers running production models
- teams without heavy MLOps infrastructure
- systems where clarity and trust matter more than complexity

It is intentionally **not** a full MLOps platform.

---

## In one sentence

**SentryML watches how your production data changes — and tells you clearly when it matters.**
