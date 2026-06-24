from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    ready_for_scoring: bool
    model_name: str | None = None
    model_version: str | None = None
    artifact_path: str
    runtime_mode: Literal["local", "docker"] = "local"
    redis_score_cache_enabled: bool = False
    bigquery_event_sink_enabled: bool = False
    bigquery_configured: bool = False


class RuntimeStatusResponse(BaseModel):
    runtime_mode: Literal["local", "docker"]
    scoring_ready: bool
    model_name: str | None = None
    model_version: str | None = None
    redis_score_cache_enabled: bool
    redis_status: Literal["ok", "disabled", "not_installed", "error"]
    redis_queue_depth: int | None = None
    celery_event_sink_enabled: bool
    celery_worker_status: Literal["ok", "disabled", "not_installed", "offline", "error"]
    celery_worker_count: int = 0
    bigquery_configured: bool
    bigquery_status: Literal["ready", "disabled", "not_configured"]
    last_checked_at: str


class ScoreOperationStatus(BaseModel):
    runtime_mode: Literal["local", "docker"]
    score_source: Literal["model", "redis_cache"]
    event_status: Literal["queued", "disabled", "failed"]
    event_sink: Literal["celery_bigquery", "disabled"]
    event_id: str | None = None
    scored_at: str


class ScoreRequest(BaseModel):
    transaction_id: int | None = Field(default=None, description="Optional transaction identifier.")
    transaction_amount: float = Field(..., ge=0, description="Transaction amount.")
    product_cd: str = Field(..., min_length=1, description="ProductCD value from the IEEE-CIS dataset.")
    card1: int = Field(..., description="Primary card hash used in the current MVP feature set.")
    card4: str | None = Field(default=None, description="Card network, for example visa or discover.")
    card6: str | None = Field(default=None, description="Card type, for example debit or credit.")
    p_emaildomain: str | None = Field(default=None, description="Purchaser email domain.")
    r_emaildomain: str | None = Field(default=None, description="Recipient email domain.")
    threshold: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Optional threshold override. If omitted, the API uses the artifact threshold.",
    )


class ScoreResponse(BaseModel):
    transaction_id: int | None = None
    fraud_score: float
    threshold_used: float
    risk_label: Literal["low", "medium", "high"]
    needs_manual_review: bool
    model_name: str
    model_version: str
    active_signals: list[str]
    feature_values: dict[str, float]
    operation_status: ScoreOperationStatus | None = None


class ExplainResponse(BaseModel):
    transaction_id: int | None = None
    fraud_score: float
    threshold_used: float
    risk_label: Literal["low", "medium", "high"]
    needs_manual_review: bool
    model_name: str
    model_version: str
    active_signals: list[str]
    explanation_text: str
    explanation_points: list[str]
    feature_values: dict[str, float]
    operation_status: ScoreOperationStatus | None = None
