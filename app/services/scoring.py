from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json


SCORE_SCALE = Decimal("0.00000001")


@dataclass(frozen=True)
class VariableWeight:
    code: str
    weight: Decimal


@dataclass(frozen=True)
class RuleSet:
    version: str
    variables: list[VariableWeight]


@dataclass(frozen=True)
class ScoreResult:
    subject_id: str
    rule_version: str
    score: Decimal
    input_fingerprint: str
    contributions: dict[str, Decimal]


class DeterministicScoringEngine:
    """Scores datasets with stable ordering and fixed Decimal precision."""

    def score(self, subject_id: str, dataset: dict[str, Decimal], rules: RuleSet) -> ScoreResult:
        contributions: dict[str, Decimal] = {}

        for variable in sorted(rules.variables, key=lambda item: item.code):
            value = dataset.get(variable.code, Decimal("0"))
            contribution = (value * variable.weight).quantize(SCORE_SCALE, rounding=ROUND_HALF_UP)
            contributions[variable.code] = contribution

        total = sum(contributions.values(), Decimal("0")).quantize(SCORE_SCALE, rounding=ROUND_HALF_UP)

        return ScoreResult(
            subject_id=subject_id,
            rule_version=rules.version,
            score=total,
            input_fingerprint=self._fingerprint(dataset=dataset, rules=rules),
            contributions=contributions,
        )

    def _fingerprint(self, dataset: dict[str, Decimal], rules: RuleSet) -> str:
        payload = {
            "dataset": {key: self._decimal_to_string(dataset[key]) for key in sorted(dataset)},
            "rule_version": rules.version,
            "variables": [
                {"code": variable.code, "weight": self._decimal_to_string(variable.weight)}
                for variable in sorted(rules.variables, key=lambda item: item.code)
            ],
        }
        canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _decimal_to_string(self, value: Decimal) -> str:
        return format(value.quantize(SCORE_SCALE, rounding=ROUND_HALF_UP), "f")
