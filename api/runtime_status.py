from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache

from api.model_bundle import load_model_bundle
from api.schemas import RuntimeStatusResponse
from api.settings import get_runtime_settings


@lru_cache(maxsize=1)
def _get_model_bundle_cached():
    return load_model_bundle()


def _probe_redis_status() -> tuple[str, int | None]:
    settings = get_runtime_settings()
    if not settings.redis_score_cache_enabled:
        return "disabled", None

    try:
        import redis
    except ImportError:
        return "not_installed", None

    try:
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        queue_depth = client.llen("score-events")
        return "ok", int(queue_depth)
    except Exception:
        return "error", None


def _probe_celery_status() -> tuple[str, int]:
    settings = get_runtime_settings()
    if not settings.celery_event_sink_enabled:
        return "disabled", 0

    try:
        from api.celery_app import celery_app
    except ImportError:
        return "not_installed", 0

    try:
        inspector = celery_app.control.inspect(timeout=1)
        ping_result = inspector.ping() or {}
        worker_count = len(ping_result)
        if worker_count == 0:
            return "offline", 0
        return "ok", worker_count
    except Exception:
        return "error", 0


def build_runtime_status() -> RuntimeStatusResponse:
    settings = get_runtime_settings()
    try:
        bundle = _get_model_bundle_cached()
        scoring_ready = True
        model_name = bundle.model_name
        model_version = bundle.model_version
    except FileNotFoundError:
        scoring_ready = False
        model_name = None
        model_version = None

    redis_status, redis_queue_depth = _probe_redis_status()
    celery_worker_status, celery_worker_count = _probe_celery_status()
    if not settings.enable_bigquery_event_sink or settings.runtime_mode != "docker":
        bigquery_status = "disabled"
    elif settings.bigquery_configured:
        bigquery_status = "ready"
    else:
        bigquery_status = "not_configured"

    return RuntimeStatusResponse(
        runtime_mode=settings.runtime_mode,
        scoring_ready=scoring_ready,
        model_name=model_name,
        model_version=model_version,
        redis_score_cache_enabled=settings.redis_score_cache_enabled,
        redis_status=redis_status,
        redis_queue_depth=redis_queue_depth,
        celery_event_sink_enabled=settings.celery_event_sink_enabled,
        celery_worker_status=celery_worker_status,
        celery_worker_count=celery_worker_count,
        bigquery_configured=settings.bigquery_configured,
        bigquery_status=bigquery_status,
        last_checked_at=datetime.now(timezone.utc).isoformat(),
    )
