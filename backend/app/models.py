from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


SourceStatus = Literal["ok", "missing_action", "timeout", "error", "skipped"]


class SourceResult(BaseModel):
    status: SourceStatus
    data: dict[str, Any] | list[Any] | None = None
    error: str | None = None


class ScoreSet(BaseModel):
    # Primary three-axis scores (the authoritative signal)
    data_confidence: int = Field(ge=0, le=10)
    investment_attractiveness: int = Field(ge=0, le=10)
    regulatory_risk: int = Field(ge=0, le=10)
    # Supporting sub-scores (retained for display detail)
    fundamentals: int = Field(ge=0, le=10)
    technicals: int = Field(ge=0, le=10)
    sentiment: int = Field(ge=0, le=10)
    institutional_trust: int = Field(ge=0, le=10)
    overall: int = Field(ge=0, le=100)
    label: str


class AnalysisResponse(BaseModel):
    ticker: str
    company: str | None = None
    as_of: datetime
    price: dict[str, Any] = Field(default_factory=dict)
    news: list[dict[str, Any]] = Field(default_factory=list)
    filings: list[dict[str, Any]] = Field(default_factory=list)
    sentiment: dict[str, Any] = Field(default_factory=dict)
    regulatory: list[dict[str, Any]] = Field(default_factory=list)
    scores: ScoreSet
    brief: str
    sources: dict[str, SourceResult]
