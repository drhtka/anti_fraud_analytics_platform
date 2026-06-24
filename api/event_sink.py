from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from api.schemas import ScoreRequest, ScoreResponse
from api.settings import get_runtime_settings


@dataclass(frozen=True, slots=True)
class ScoreEventDispatchResult:
    status: str
    sink: str
    event_id: str | None = None


def enqueue_score_event(request: ScoreRequest, response: ScoreResponse) -> ScoreEventDispatchResult:
    settings = get_runtime_settings()
    if not settings.celery_event_sink_enabled:
        return ScoreEventDispatchResult(status="disabled", sink="disabled")

    try:
        from api.tasks import persist_score_event
    except ImportError:
        return ScoreEventDispatchResult(status="failed", sink="celery_bigquery")

    event_id = str(uuid4())

    event_payload = {
        "event_id": event_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "transaction_id": request.transaction_id,
        "fraud_score": response.fraud_score,
        "threshold_used": response.threshold_used,
        "risk_label": response.risk_label,
        "needs_manual_review": response.needs_manual_review,
        "model_name": response.model_name,
        "model_version": response.model_version,
        "runtime_mode": settings.runtime_mode,
        "request_payload": json.dumps(request.model_dump(mode="json"), sort_keys=True),
        "score_payload": json.dumps(response.model_dump(mode="json"), sort_keys=True),
    }

    try:
        persist_score_event.delay(event_payload)
    except Exception:
        return ScoreEventDispatchResult(
            status="failed",
            sink="celery_bigquery",
            event_id=event_id,
        )

    return ScoreEventDispatchResult(
        status="queued",
        sink="celery_bigquery",
        event_id=event_id,
    )
