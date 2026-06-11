from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from api.ui_content.shared import build_duckdb_connection, render_html_table, resolve_dataset_dir


@lru_cache(maxsize=1)
def load_sql_sections(data_dir: str) -> list[dict[str, object]]:
    base_data_path = Path(data_dir)
    dataset_dir = resolve_dataset_dir(base_data_path)
    if dataset_dir is None:
        return [
            {
                "title": "SQL results are unavailable",
                "table_name": "missing_local_data",
                "source_file": "sql/",
                "description": "The SQL screen needs local IEEE-CIS CSV files in data/raw/ to render result tables.",
                "query": "Place train_transaction.csv and train_identity.csv into data/raw/ to enable live SQL sections.",
                "reading_notes": [
                    "The UI is ready for live DuckDB-backed SQL blocks.",
                    "As a fallback, the same files can also be placed directly in data/.",
                    "Once local CSV files are present, the same screen can show real result tables.",
                ],
                "result_html": None,
            }
        ]

    sql_sections = [
        {
            "title": "1. Overall fraud rate",
            "table_name": "overall_fraud_rate",
            "source_file": "sql/ieee_cis_week_1_duckdb.sql",
            "description": "This is the first sanity-check table: how many transactions exist and how rare the fraud class is.",
            "query": """
                SELECT COUNT(*) AS total_transactions,
                  SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) AS fraud_transactions,
                  ROUND(
                    100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                    4
                  ) AS fraud_rate_pct
                FROM train_transaction
            """,
            "reading_notes": [
                "Use this table to explain class imbalance before any modeling.",
                "It gives context for why precision, recall, and threshold tuning matter in anti-fraud tasks.",
            ],
        },
        {
            "title": "2. Fraud rate by ProductCD",
            "table_name": "fraud_rate_by_productcd",
            "source_file": "sql/ieee_cis_week_1_duckdb.sql",
            "description": "This segment table shows which product groups behave like higher-risk transaction buckets.",
            "query": """
                SELECT ProductCD,
                  COUNT(*) AS tx_count,
                  SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) AS fraud_tx_count,
                  ROUND(
                    100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                    2
                  ) AS fraud_rate_pct
                FROM train_transaction
                GROUP BY ProductCD
                ORDER BY fraud_rate_pct DESC, tx_count DESC
            """,
            "reading_notes": [
                "This is one of the first business-readable segment cuts in the project.",
                "Later this pattern feeds both fraud hypotheses and lightweight scoring signals.",
            ],
        },
        {
            "title": "3. Fraud rate by recipient email domain",
            "table_name": "fraud_rate_by_r_emaildomain",
            "source_file": "sql/ieee_cis_week_1_duckdb.sql",
            "description": "Recipient email domains can expose suspicious routing patterns and weak trust signals.",
            "query": """
                SELECT R_emaildomain,
                  COUNT(*) AS tx_count,
                  SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) AS fraud_tx_count,
                  ROUND(
                    100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                    2
                  ) AS fraud_rate_pct
                FROM train_transaction
                GROUP BY R_emaildomain
                HAVING COUNT(*) >= 100
                ORDER BY fraud_rate_pct DESC, tx_count DESC
                LIMIT 15
            """,
            "reading_notes": [
                "This block is good for explaining why some domains became high-risk candidates.",
                "It directly connects SQL exploration to later model signals and rules.",
            ],
        },
        {
            "title": "4. Large transactions vs customer baseline",
            "table_name": "amount_anomalies_vs_customer_baseline",
            "source_file": "sql/02_suspicious_patterns.sql",
            "description": "This query looks for transactions that are unusually large compared with a customer proxy history.",
            "query": """
                WITH customer_stats AS (
                  SELECT card1 AS customer_proxy,
                    AVG(TransactionAmt) AS avg_amount,
                    STDDEV_SAMP(TransactionAmt) AS std_amount
                  FROM train_transaction
                  GROUP BY card1
                )
                SELECT t.TransactionID,
                  t.card1 AS customer_proxy,
                  t.TransactionAmt,
                  s.avg_amount,
                  s.std_amount
                FROM train_transaction t
                  JOIN customer_stats s ON t.card1 = s.customer_proxy
                WHERE t.TransactionAmt > s.avg_amount + 3 * COALESCE(s.std_amount, 0)
                ORDER BY t.TransactionAmt DESC
                LIMIT 15
            """,
            "reading_notes": [
                "This is a classic anti-fraud idea: compare current amount with a personal baseline.",
                "Later the same logic appears as `feat_amount_gt_card1_avg_plus_3std` in the MVP scoring flow.",
            ],
        },
    ]

    connection = build_duckdb_connection(dataset_dir)
    try:
        for section in sql_sections:
            result = connection.execute(section["query"])
            columns = [column[0] for column in result.description]
            rows = result.fetchall()
            section["result_html"] = render_html_table(columns, rows, displayed_rows=12)
    finally:
        connection.close()

    return sql_sections
