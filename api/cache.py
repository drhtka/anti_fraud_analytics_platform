from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import Any

from api.schemas import ScoreRequest, ScoreResponse
from api.settings import get_runtime_settings

try:
    import redis
    from redis.exceptions import RedisError
except ImportError:  # pragma: no cover - optional dependency for docker mode only
    redis = None

    class RedisError(Exception):
        pass


def _build_request_cache_key(request: ScoreRequest) -> str:
    payload = request.model_dump(mode="json")
    raw_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
    return f"score-response:{payload_hash}"


@lru_cache(maxsize=1)
def _get_redis_client() -> Any | None:
    settings = get_runtime_settings()
    if not settings.redis_score_cache_enabled or redis is None:
        return None
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def load_cached_score_response(request: ScoreRequest) -> ScoreResponse | None:
    client = _get_redis_client()
    if client is None:
        return None

    try:
        raw_payload = client.get(_build_request_cache_key(request))
    except RedisError:
        return None

    if not raw_payload:
        return None

    try:
        return ScoreResponse.model_validate_json(raw_payload)
    except ValueError:
        return None


def store_cached_score_response(request: ScoreRequest, response: ScoreResponse) -> None:
    client = _get_redis_client()
    settings = get_runtime_settings()
    if client is None:
        return

    try:
        client.setex(
            _build_request_cache_key(request),
            settings.redis_cache_ttl_seconds,
            response.model_dump_json(),
        )
    except RedisError:
        return
