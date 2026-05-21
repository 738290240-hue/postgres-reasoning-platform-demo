from decimal import Decimal
import unittest

from app.services.scoring import DeterministicScoringEngine, RuleSet, VariableWeight


class DeterministicScoringEngineTest(unittest.TestCase):
    def test_same_dataset_and_config_version_produce_identical_result(self):
        rules = RuleSet(
            version="2026.05.0",
            variables=[
                VariableWeight(code="age_risk", weight=Decimal("1.5000")),
                VariableWeight(code="lab_signal", weight=Decimal("2.2500")),
                VariableWeight(code="history_flag", weight=Decimal("-0.5000")),
            ],
        )
        dataset = {
            "lab_signal": Decimal("3.2000"),
            "history_flag": Decimal("1.0000"),
            "age_risk": Decimal("2.0000"),
        }

        engine = DeterministicScoringEngine()
        first = engine.score(subject_id="subject-001", dataset=dataset, rules=rules)
        second = engine.score(subject_id="subject-001", dataset=dict(reversed(dataset.items())), rules=rules)

        self.assertEqual(first, second)
        self.assertEqual(first.score, Decimal("9.70000000"))
        self.assertEqual(
            first.input_fingerprint,
            "f476d2f8ca342192736cdc7da6b1b156f6db47c7400e40dce2477a471dec3cc9",
        )
        self.assertEqual(first.rule_version, "2026.05.0")

    def test_missing_variable_defaults_to_zero_without_random_side_effects(self):
        rules = RuleSet(
            version="2026.05.0",
            variables=[
                VariableWeight(code="documented_signal", weight=Decimal("4.0000")),
                VariableWeight(code="not_collected_yet", weight=Decimal("99.0000")),
            ],
        )

        result = DeterministicScoringEngine().score(
            subject_id="subject-002",
            dataset={"documented_signal": Decimal("2.5000")},
            rules=rules,
        )

        self.assertEqual(result.score, Decimal("10.00000000"))
        self.assertEqual(
            result.contributions,
            {
                "documented_signal": Decimal("10.00000000"),
                "not_collected_yet": Decimal("0E-8"),
            },
        )


if __name__ == "__main__":
    unittest.main()
