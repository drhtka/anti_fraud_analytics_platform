from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal


API_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = API_DIR.parent
ARTIFACTS_DIR = API_DIR / "artifacts"
DEFAULT_MODEL_ARTIFACT_PATH = Path(
    os.getenv("MODEL_ARTIFACT_PATH", ARTIFACTS_DIR / "random_forest_mvp.joblib")
)


def _env_flag(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    runtime_mode: Literal["local", "docker"]
    redis_url: str | None
    redis_cache_ttl_seconds: int
    enable_redis_score_cache: bool
    enable_bigquery_event_sink: bool
    celery_broker_url: str | None
    celery_result_backend: str | None
    bigquery_project_id: str | None
    bigquery_dataset: str | None
    bigquery_table: str | None
    bigquery_auto_create: bool

    @property
    def redis_score_cache_enabled(self) -> bool:
        return (
            self.runtime_mode == "docker"
            and self.enable_redis_score_cache
            and bool(self.redis_url)
        )

    @property
    def celery_event_sink_enabled(self) -> bool:
        return (
            self.runtime_mode == "docker"
            and self.enable_bigquery_event_sink
            and bool(self.celery_broker_url)
            and self.bigquery_configured
        )

    @property
    def bigquery_configured(self) -> bool:
        return bool(
            self.bigquery_project_id
            and self.bigquery_dataset
            and self.bigquery_table
        )


@lru_cache(maxsize=1)
def get_runtime_settings() -> RuntimeSettings:
    runtime_mode_value = os.getenv("SCORING_RUNTIME_MODE", "local").strip().lower() or "local"
    runtime_mode: Literal["local", "docker"] = (
        "docker" if runtime_mode_value == "docker" else "local"
    )
    redis_url = os.getenv("REDIS_URL")
    celery_broker_url = os.getenv("CELERY_BROKER_URL") or redis_url
    celery_result_backend = os.getenv("CELERY_RESULT_BACKEND") or celery_broker_url

    return RuntimeSettings(
        runtime_mode=runtime_mode,
        redis_url=redis_url,
        redis_cache_ttl_seconds=int(os.getenv("REDIS_SCORE_CACHE_TTL_SECONDS", "900")),
        enable_redis_score_cache=_env_flag("ENABLE_REDIS_SCORE_CACHE", True),
        enable_bigquery_event_sink=_env_flag("ENABLE_BIGQUERY_EVENT_SINK", True),
        celery_broker_url=celery_broker_url,
        celery_result_backend=celery_result_backend,
        bigquery_project_id=os.getenv("BIGQUERY_PROJECT_ID"),
        bigquery_dataset=os.getenv("BIGQUERY_DATASET"),
        bigquery_table=os.getenv("BIGQUERY_TABLE"),
        bigquery_auto_create=_env_flag("BIGQUERY_AUTO_CREATE", True),
    )
