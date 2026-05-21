from decimal import Decimal
import unittest

from app.services.rule_repository import RuleRepository
from app.services.scoring import RuleSet, VariableWeight


class FakeMappingResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class FakeScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class FakeSession:
    def __init__(self, rows=None, scalar=None):
        self.rows = rows or []
        self.scalar = scalar
        self.executed = []

    def execute(self, sql, params):
        self.executed.append((sql, params))
        if self.scalar is not None and len(self.executed) == 1:
            return FakeScalarResult(self.scalar)
        return FakeMappingResult(self.rows)


class RuleRepositoryTest(unittest.TestCase):
    def test_loads_active_rule_set_from_database_rows(self):
        session = FakeSession(
            [
                {"version": "2026.05.0", "code": "age_risk", "weight": Decimal("1.5000")},
                {"version": "2026.05.0", "code": "lab_signal", "weight": Decimal("2.2500")},
            ]
        )

        rules = RuleRepository().load_rule_set(session, version=None)

        self.assertEqual(rules.version, "2026.05.0")
        self.assertEqual([variable.code for variable in rules.variables], ["age_risk", "lab_signal"])
        self.assertEqual(rules.variables[1].weight, Decimal("2.2500"))
        self.assertEqual(session.executed[0][1], {"version": None})

    def test_loads_latest_dataset_from_database_rows(self):
        session = FakeSession(
            [
                {"code": "age_risk", "numeric_value": Decimal("2.0000")},
                {"code": "lab_signal", "numeric_value": Decimal("3.2000")},
            ]
        )

        dataset = RuleRepository().load_latest_dataset(session, subject_reference="subject-001")

        self.assertEqual(
            dataset,
            {"age_risk": Decimal("2.0000"), "lab_signal": Decimal("3.2000")},
        )
        self.assertEqual(session.executed[0][1], {"subject_reference": "subject-001"})

    def test_records_score_run_and_contributions(self):
        session = FakeSession(scalar="score-run-001")
        repository = RuleRepository()
        rules = RuleSet(
            version="2026.05.0",
            variables=[
                VariableWeight(code="age_risk", weight=Decimal("1.5000")),
                VariableWeight(code="lab_signal", weight=Decimal("2.2500")),
            ],
        )

        stored = repository.record_score_run(
            session,
            subject_reference="demo-clinic:subject-001",
            rule_set=rules,
            dataset={"age_risk": Decimal("2.0000"), "lab_signal": Decimal("3.2000")},
            score=Decimal("10.20000000"),
            input_fingerprint="abc123",
            contributions={
                "age_risk": Decimal("3.00000000"),
                "lab_signal": Decimal("7.20000000"),
            },
            run_reason="unit test",
            run_by="test-runner",
        )

        self.assertEqual(stored.score_run_id, "score-run-001")
        self.assertEqual(len(session.executed), 3)
        self.assertEqual(session.executed[0][1]["rule_version"], "2026.05.0")
        self.assertEqual(session.executed[1][1]["variable_code"], "age_risk")
        self.assertEqual(session.executed[2][1]["variable_code"], "lab_signal")


if __name__ == "__main__":
    unittest.main()
