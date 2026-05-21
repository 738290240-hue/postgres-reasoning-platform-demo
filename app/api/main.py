from decimal import Decimal

from fastapi import FastAPI
from pydantic import BaseModel, Field

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
