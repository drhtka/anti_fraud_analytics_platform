from __future__ import annotations

from api.bigquery_sink import persist_score_event_to_bigquery
from api.celery_app import celery_app


@celery_app.task(name="api.tasks.persist_score_event")
def persist_score_event(event_payload: dict[str, object]) -> None:
    persist_score_event_to_bigquery(event_payload)
