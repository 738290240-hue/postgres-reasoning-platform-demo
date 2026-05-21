from decimal import Decimal

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.services.rule_repository import RuleRepository
from app.services.scoring import DeterministicScoringEngine, RuleSet, VariableWeight


app = FastAPI(
    title="PostgreSQL Reasoning Platform Demo",
    version="0.1.0",
    description="Prototype API for deterministic, versioned scoring on PostgreSQL-backed data.",
)


class VariableWeightRequest(BaseModel):
    code: str = Field(min_length=1, max_length=120)
    weight: Decimal


class ScoreRequest(BaseModel):
    subject_id: str = Field(min_length=1, max_length=120)
    rule_version: str = Field(min_length=1, max_length=80)
    variables: list[VariableWeightRequest]
    dataset: dict[str, Decimal]


class DatabaseScoreRequest(BaseModel):
    subject_reference: str = Field(min_length=1, max_length=120)
    rule_version: str | None = Field(default=None, min_length=1, max_length=80)
    run_reason: str = Field(default="manual scoring request", min_length=1, max_length=240)
    run_by: str = Field(default="api", min_length=1, max_length=120)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/score")
def score(request: ScoreRequest) -> dict[str, object]:
    rules = RuleSet(
        version=request.rule_version,
        variables=[
            VariableWeight(code=variable.code, weight=variable.weight)
            for variable in request.variables
        ],
    )
    result = DeterministicScoringEngine().score(
        subject_id=request.subject_id,
        dataset=request.dataset,
        rules=rules,
    )
    return {
        "subject_id": result.subject_id,
        "rule_version": result.rule_version,
        "score": str(result.score),
        "input_fingerprint": result.input_fingerprint,
        "contributions": {key: str(value) for key, value in result.contributions.items()},
    }


@app.post("/score/from-database")
def score_from_database(
    request: DatabaseScoreRequest,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    repository = RuleRepository()
    rules = repository.load_rule_set(session, version=request.rule_version)
    dataset = repository.load_latest_dataset(session, subject_reference=request.subject_reference)

    result = DeterministicScoringEngine().score(
        subject_id=request.subject_reference,
        dataset=dataset,
        rules=rules,
    )

    stored = repository.record_score_run(
        session,
        subject_reference=request.subject_reference,
        rule_set=rules,
        dataset=dataset,
        score=result.score,
        input_fingerprint=result.input_fingerprint,
        contributions=result.contributions,
        run_reason=request.run_reason,
        run_by=request.run_by,
    )
    session.commit()

    return {
        "score_run_id": stored.score_run_id,
        "subject_reference": request.subject_reference,
        "rule_version": result.rule_version,
        "score": str(result.score),
        "input_fingerprint": result.input_fingerprint,
        "contributions": {key: str(value) for key, value in result.contributions.items()},
    }
