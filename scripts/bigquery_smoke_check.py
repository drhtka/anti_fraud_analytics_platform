from __future__ import annotations

import os
import sys

from google.cloud import bigquery


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Environment variable {name} is required.")
    return value


def main() -> int:
    project_id = require_env("BIGQUERY_PROJECT_ID")
    dataset = require_env("BIGQUERY_DATASET")
    table = require_env("BIGQUERY_TABLE")
    credentials_path = require_env("GOOGLE_APPLICATION_CREDENTIALS")

    client = bigquery.Client(project=project_id)
    query = """
        SELECT
          1 AS smoke_ok,
          CURRENT_TIMESTAMP() AS checked_at,
          @dataset AS dataset_name,
          @table AS table_name
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("dataset", "STRING", dataset),
            bigquery.ScalarQueryParameter("table", "STRING", table),
        ]
    )
    rows = list(client.query(query, job_config=job_config).result())
    row = rows[0]

    print("BigQuery smoke check passed")
    print(f"project_id={project_id}")
    print(f"dataset={dataset}")
    print(f"table={table}")
    print(f"credentials_path={credentials_path}")
    print(f"smoke_ok={row.smoke_ok}")
    print(f"checked_at={row.checked_at}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"BigQuery smoke check failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
