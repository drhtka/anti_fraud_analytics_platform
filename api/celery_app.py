from __future__ import annotations

from celery import Celery

from api.settings import get_runtime_settings


settings = get_runtime_settings()

celery_app = Celery(
    "anti_fraud_analytics_platform",
    broker=settings.celery_broker_url or "memory://",
    backend=settings.celery_result_backend or "cache+memory://",
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_ignore_result=True,
    task_default_queue="score-events",
    imports=("api.tasks",),
    broker_connection_retry_on_startup=True,
)
