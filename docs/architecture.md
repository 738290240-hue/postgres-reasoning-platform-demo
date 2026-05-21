# Architecture Notes

This demo models a backend foundation for a reasoning platform where business users can
change scoring configuration without code changes, while engineers preserve reproducibility,
auditability, and PostgreSQL-level data integrity.

## Schema Boundaries

- `identity` stores subject identifiers and PHI-like profile fields.
- `reasoning` stores variable definitions, versioned rule sets, observations, score runs, and
  per-variable score contributions.
- `audit` stores normalized change history for important reasoning tables.

The separation is intentional. It allows more restrictive grants on `identity.subject_phi` while
keeping derived reasoning outputs queryable by operational users.

## Versioned Configuration

`reasoning.rule_set` owns immutable scoring versions. `reasoning.rule_weight` attaches variables
to a specific version with decimal weights and optional bounds. Score runs always reference a
specific `rule_set_id`, so historical results remain explainable after future configuration changes.

The `/score/from-database` endpoint loads either a requested rule-set version or the single active
version from PostgreSQL, then reads the subject's latest numeric observations. This keeps runtime
behavior aligned with the relational configuration instead of relying on request-body rules.

## Deterministic Scoring

The scoring service sorts variables by stable code, uses `Decimal`, quantizes output to eight
decimal places, and hashes a canonical JSON payload. This makes repeated runs reproducible for the
same dataset and rule version.

## Audit Trail

The migration installs a generic `audit.capture_change()` trigger on configuration and score-run
tables. Each audit row records:

- schema and table name
- row primary key
- INSERT, UPDATE, or DELETE
- actor and reason
- before and after JSON snapshots
- timestamp

For a production system, actor and reason would be set at transaction start with `SET LOCAL`.

## Security Posture

The second migration creates separate roles for:

- `reasoning_app`: read configuration and observations, write score provenance
- `reasoning_admin`: maintain configuration and inspect audit data
- `phi_reader`: read PHI fields only when explicitly granted
- `audit_reader`: inspect `audit.change_log`

RLS policies use `app.tenant_id` as an optional transaction-scoped boundary. For example,
`demo-clinic:subject-001` is visible when `SET LOCAL app.tenant_id = 'demo-clinic'`.

## Scaling Posture

Variables are rows, not columns. Adding 10 or 10,000 variables does not require schema changes.
Indexes focus on subject, variable, observed time, rule version, and audit lookup patterns.
