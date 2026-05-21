# Trial Deliverable Outline

This repository is shaped as a short trial artifact for a senior PostgreSQL/backend role.

## What It Demonstrates

- Configurable scoring rules stored in relational tables rather than hardcoded application logic.
- API scoring that can load active rules and latest observations directly from PostgreSQL.
- Versioned rule sets so historical calculations can be reproduced.
- Deterministic scoring behavior with stable ordering, `Decimal` math, and canonical fingerprints.
- Audit tables and triggers for who/what/when/why change history.
- Structural isolation of PHI-like data from derived reasoning data.
- Role grants and RLS policies showing security boundaries.
- Normalized variable storage that scales without dynamic schema redesign.

## What Is Intentionally Out of Scope

- Frontend UI.
- AI model inference.
- Application authentication.
- Full FHIR resource ingestion.

## Suggested Next Steps for a Real Client Project

1. Review the client's existing schema against these boundaries.
2. Identify hardcoded rule or weighting logic and move it into versioned configuration tables.
3. Add transaction-scoped audit actor and reason propagation.
4. Build migration and integration tests against a disposable PostgreSQL instance.
5. Benchmark score runs with realistic variable and observation volumes.
