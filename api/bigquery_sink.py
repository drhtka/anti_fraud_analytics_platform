from __future__ import annotations

from functools import lru_cache
from typing import Any

from api.settings import get_runtime_settings


@lru_cache(maxsize=1)
def _get_bigquery_table_id() -> str:
    settings = get_runtime_settings()
    if not settings.bigquery_configured:
        raise RuntimeError("BigQuery settings are incomplete.")
    return (
        f"{settings.bigquery_project_id}."
        f"{settings.bigquery_dataset}."
        f"{settings.bigquery_table}"
    )


def _build_table_schema(bigquery: Any) -> list[Any]:
    return [
        bigquery.SchemaField("event_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("transaction_id", "INT64", mode="NULLABLE"),
        bigquery.SchemaField("fraud_score", "FLOAT64", mode="REQUIRED"),
        bigquery.SchemaField("threshold_used", "FLOAT64", mode="REQUIRED"),
        bigquery.SchemaField("risk_label", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("needs_manual_review", "BOOL", mode="REQUIRED"),
        bigquery.SchemaField("model_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("model_version", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("runtime_mode", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("request_payload", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("score_payload", "STRING", mode="REQUIRED"),
    ]


def _ensure_bigquery_table(client: Any, bigquery: Any) -> None:
    settings = get_runtime_settings()
    if not settings.bigquery_auto_create:
        return

    dataset_id = f"{settings.bigquery_project_id}.{settings.bigquery_dataset}"
    client.create_dataset(bigquery.Dataset(dataset_id), exists_ok=True)
    table = bigquery.Table(_get_bigquery_table_id(), schema=_build_table_schema(bigquery))
    client.create_table(table, exists_ok=True)


def persist_score_event_to_bigquery(event_payload: dict[str, object]) -> None:
    settings = get_runtime_settings()
    if not settings.bigquery_configured:
        return

    from google.cloud import bigquery  # pragma: no cover - docker dependency

    client = bigquery.Client(project=settings.bigquery_project_id)
    _ensure_bigquery_table(client, bigquery)
    errors = client.insert_rows_json(_get_bigquery_table_id(), [event_payload])
    if errors:
        raise RuntimeError(f"BigQuery insert failed: {errors}")
