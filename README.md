# PostgreSQL Reasoning Platform Demo

A portfolio-grade backend demo for a deterministic, auditable reasoning platform built on
PostgreSQL. The project is intentionally focused on database architecture, backend boundaries, and
reproducible scoring rather than frontend or AI features.

## Why This Exists

This repository demonstrates the kind of backend foundation I would propose for a trial project
involving high-value reasoning workflows:

- rule weights and thresholds are stored as versioned configuration, not hardcoded logic
- score runs bind to a specific rule-set version for reproducibility
- audit triggers capture configuration and score-run changes
- PHI-like subject fields are structurally isolated from derived reasoning data
- variables are normalized rows, allowing growth from a small prototype to large catalogs

## Stack

- PostgreSQL 16
- Python 3.11+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- Docker Compose
- Standard-library unit tests for the deterministic scoring core

## Repository Map

```text
app/api/main.py                                  FastAPI boundary and score endpoint
app/services/scoring.py                         Deterministic scoring engine
app/db/session.py                               SQLAlchemy engine/session setup
alembic/versions/20260521_0001_initial...py     PostgreSQL schema migration
docs/architecture.md                            Design notes and tradeoffs
docs/trial-deliverable.md                       Trial-project explanation
tests/test_scoring_engine.py                    Deterministic behavior tests
```

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
docker compose up -d postgres
alembic upgrade head
uvicorn app.api.main:app --reload
```

Run the deterministic scoring tests:

```bash
python3 -m unittest discover -s tests -v
```

## Example API Request

```bash
curl -X POST http://127.0.0.1:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "subject_id": "subject-001",
    "rule_version": "2026.05.0",
    "variables": [
      {"code": "age_risk", "weight": "1.5000"},
      {"code": "lab_signal", "weight": "2.2500"},
      {"code": "history_flag", "weight": "-0.5000"}
    ],
    "dataset": {
      "lab_signal": "3.2000",
      "history_flag": "1.0000",
      "age_risk": "2.0000"
    }
  }'
```

Expected score:

```json
{
  "subject_id": "subject-001",
  "rule_version": "2026.05.0",
  "score": "9.70000000"
}
```

## Architectural Highlights

### Maintainable Configuration

`reasoning.rule_set` and `reasoning.rule_weight` keep score versions, weights, and thresholds in
tables. A future admin UI can safely update draft configurations without changing application code.

### Audit Trail

The `audit.change_log` table captures table name, row key, action, actor, reason, before snapshot,
after snapshot, and timestamp. Triggers currently cover rule sets, rule weights, variable
definitions, and score runs.

### Deterministic Reliability

The scoring engine sorts variables by code, uses decimal arithmetic, quantizes values to a fixed
scale, and produces a canonical SHA-256 input fingerprint. Same input plus same config version
produces the same output.

### Security Readiness

The schema separates `identity.subject_phi` from reasoning tables. In production, this allows
separate grants, access policies, retention rules, and audit review for PHI/PII.

### Extensibility

Variables are records in `reasoning.variable_definition`, not columns. New variables can be added
without migrations, and score contributions remain explainable at the per-variable level.

## Notes

This is a concise technical demo, not a complete production system. Production work would add
authentication, authorization, row-level security, integration tests against PostgreSQL, and deeper
FHIR/HL7 mapping if healthcare interoperability is required.
