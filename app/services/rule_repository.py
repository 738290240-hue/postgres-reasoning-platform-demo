from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.services.scoring import RuleSet, VariableWeight


LOAD_RULE_SET_SQL = """
SELECT
    rs.rule_set_id,
    rs.version,
    vd.code,
    rw.weight
FROM reasoning.rule_set rs
JOIN reasoning.rule_weight rw ON rw.rule_set_id = rs.rule_set_id
JOIN reasoning.variable_definition vd ON vd.variable_id = rw.variable_id
WHERE
    (:version IS NOT NULL AND rs.version = :version)
    OR (:version IS NULL AND rs.status = 'active')
ORDER BY vd.code;
"""


LOAD_LATEST_DATASET_SQL = """
WITH latest_observation AS (
    SELECT DISTINCT ON (vd.code)
        vd.code,
        o.numeric_value
    FROM identity.subject s
    JOIN reasoning.observation o ON o.subject_id = s.subject_id
    JOIN reasoning.variable_definition vd ON vd.variable_id = o.variable_id
    WHERE
        s.external_reference = :subject_reference
        AND o.numeric_value IS NOT NULL
    ORDER BY vd.code, o.observed_at DESC, o.created_at DESC
)
SELECT code, numeric_value
FROM latest_observation
ORDER BY code;
"""


INSERT_SCORE_RUN_SQL = """
INSERT INTO reasoning.score_run (
    subject_id,
    rule_set_id,
    input_fingerprint,
    total_score,
    run_reason,
    run_by
)
SELECT
    s.subject_id,
    rs.rule_set_id,
    :input_fingerprint,
    :total_score,
    :run_reason,
    :run_by
FROM identity.subject s
JOIN reasoning.rule_set rs ON rs.version = :rule_version
WHERE s.external_reference = :subject_reference
ON CONFLICT (subject_id, rule_set_id, input_fingerprint)
DO UPDATE SET run_reason = EXCLUDED.run_reason
RETURNING score_run_id;
"""


INSERT_SCORE_CONTRIBUTION_SQL = """
INSERT INTO reasoning.score_contribution (
    score_run_id,
    variable_id,
    observed_value,
    weight,
    contribution
)
SELECT
    :score_run_id,
    vd.variable_id,
    :observed_value,
    :weight,
    :contribution
FROM reasoning.variable_definition vd
WHERE vd.code = :variable_code
ON CONFLICT (score_run_id, variable_id)
DO UPDATE SET
    observed_value = EXCLUDED.observed_value,
    weight = EXCLUDED.weight,
    contribution = EXCLUDED.contribution;
"""


@dataclass(frozen=True)
class StoredScoreRun:
    score_run_id: str


class RuleRepository:
    """Database access for rule versions, observations, and persisted score provenance."""

    def load_rule_set(self, session: Any, version: str | None = None) -> RuleSet:
        rows = self._mapping_rows(
            session.execute(self._sql(LOAD_RULE_SET_SQL), {"version": version})
        )
        if not rows:
            label = f"version {version!r}" if version else "active version"
            raise LookupError(f"No rule set found for {label}")

        versions = {row["version"] for row in rows}
        if len(versions) != 1:
            raise ValueError("Rule-set query returned more than one version")

        return RuleSet(
            version=rows[0]["version"],
            variables=[
                VariableWeight(code=row["code"], weight=Decimal(str(row["weight"])))
                for row in rows
            ],
        )

    def load_latest_dataset(self, session: Any, subject_reference: str) -> dict[str, Decimal]:
        rows = self._mapping_rows(
            session.execute(
                self._sql(LOAD_LATEST_DATASET_SQL),
                {"subject_reference": subject_reference},
            )
        )
        if not rows:
            raise LookupError(f"No numeric observations found for subject {subject_reference!r}")
        return {row["code"]: Decimal(str(row["numeric_value"])) for row in rows}

    def record_score_run(
        self,
        session: Any,
        *,
        subject_reference: str,
        rule_set: RuleSet,
        dataset: dict[str, Decimal],
        score: Decimal,
        input_fingerprint: str,
        contributions: dict[str, Decimal],
        run_reason: str,
        run_by: str,
    ) -> StoredScoreRun:
        score_run_id = session.execute(
            self._sql(INSERT_SCORE_RUN_SQL),
            {
                "subject_reference": subject_reference,
                "rule_version": rule_set.version,
                "input_fingerprint": input_fingerprint,
                "total_score": score,
                "run_reason": run_reason,
                "run_by": run_by,
            },
        ).scalar_one()

        weights_by_code = {variable.code: variable.weight for variable in rule_set.variables}
        for variable_code, contribution in contributions.items():
            session.execute(
                self._sql(INSERT_SCORE_CONTRIBUTION_SQL),
                {
                    "score_run_id": score_run_id,
                    "variable_code": variable_code,
                    "observed_value": dataset.get(variable_code, Decimal("0")),
                    "weight": weights_by_code[variable_code],
                    "contribution": contribution,
                },
            )

        return StoredScoreRun(score_run_id=str(score_run_id))

    def _sql(self, sql: str) -> Any:
        try:
            from sqlalchemy import text
        except ModuleNotFoundError:
            return sql
        return text(sql)

    def _mapping_rows(self, result: Any) -> list[dict[str, Any]]:
        return [dict(row) for row in result.mappings().all()]
