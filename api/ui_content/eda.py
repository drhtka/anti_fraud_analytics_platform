from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from api.ui_content.shared import (
    build_duckdb_connection,
    build_notes,
    render_chart,
    render_html_table,
    run_query,
)


@lru_cache(maxsize=1)
def load_eda_sections(data_dir: str) -> list[dict[str, object]]:
    data_path = Path(data_dir)
    if not (data_path / "train_transaction.csv").exists() or not (data_path / "train_identity.csv").exists():
        return [
            {
                "title": "EDA data is unavailable",
                "notes": build_notes(
                    "Place train_transaction.csv and train_identity.csv into data/ to build the EDA screen.",
                    "The EDA UI is designed to read directly from local CSV files instead of notebook outputs.",
                ),
                "outputs": [],
            }
        ]

    connection = build_duckdb_connection(data_path)
    try:
        transaction_columns = len(connection.execute("DESCRIBE train_transaction").fetchall())
        identity_columns = len(connection.execute("DESCRIBE train_identity").fetchall())

        overview_columns, overview_rows = run_query(
            connection,
            """
            SELECT COUNT(*) AS total_transactions,
              COUNT(DISTINCT card1) AS customer_proxy_count,
              ROUND(AVG(TransactionAmt), 2) AS avg_transaction_amount,
              ROUND(MAX(TransactionAmt), 2) AS max_transaction_amount
            FROM train_transaction
            """,
        )

        imbalance_columns, imbalance_rows = run_query(
            connection,
            """
            SELECT COUNT(*) AS total_transactions,
              SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) AS fraud_transactions,
              SUM(CASE WHEN isFraud = 0 THEN 1 ELSE 0 END) AS non_fraud_transactions,
              ROUND(
                100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                4
              ) AS fraud_rate_pct
            FROM train_transaction
            """,
        )

        missing_columns, missing_rows = run_query(
            connection,
            """
            SELECT 'TransactionAmt' AS field_name,
              SUM(CASE WHEN TransactionAmt IS NULL THEN 1 ELSE 0 END) AS missing_count
            FROM train_transaction
            UNION ALL
            SELECT 'ProductCD', SUM(CASE WHEN ProductCD IS NULL THEN 1 ELSE 0 END)
            FROM train_transaction
            UNION ALL
            SELECT 'card4', SUM(CASE WHEN card4 IS NULL THEN 1 ELSE 0 END)
            FROM train_transaction
            UNION ALL
            SELECT 'card6', SUM(CASE WHEN card6 IS NULL THEN 1 ELSE 0 END)
            FROM train_transaction
            UNION ALL
            SELECT 'P_emaildomain', SUM(CASE WHEN P_emaildomain IS NULL THEN 1 ELSE 0 END)
            FROM train_transaction
            UNION ALL
            SELECT 'R_emaildomain', SUM(CASE WHEN R_emaildomain IS NULL THEN 1 ELSE 0 END)
            FROM train_transaction
            UNION ALL
            SELECT 'addr1', SUM(CASE WHEN addr1 IS NULL THEN 1 ELSE 0 END)
            FROM train_transaction
            UNION ALL
            SELECT 'TransactionDT', SUM(CASE WHEN TransactionDT IS NULL THEN 1 ELSE 0 END)
            FROM train_transaction
            ORDER BY missing_count DESC, field_name
            """,
        )

        amount_bucket_columns, amount_bucket_rows = run_query(
            connection,
            """
            SELECT CASE
                WHEN TransactionAmt < 50 THEN 'lt_50'
                WHEN TransactionAmt < 100 THEN '50_100'
                WHEN TransactionAmt < 500 THEN '100_500'
                WHEN TransactionAmt < 1000 THEN '500_1000'
                ELSE 'ge_1000'
              END AS amount_bucket,
              COUNT(*) AS tx_count,
              ROUND(
                100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                2
              ) AS fraud_rate_pct
            FROM train_transaction
            GROUP BY amount_bucket
            ORDER BY fraud_rate_pct DESC, tx_count DESC
            """,
        )

        product_columns, product_rows = run_query(
            connection,
            """
            SELECT ProductCD,
              COUNT(*) AS tx_count,
              ROUND(
                100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                2
              ) AS fraud_rate_pct
            FROM train_transaction
            GROUP BY ProductCD
            ORDER BY fraud_rate_pct DESC, tx_count DESC
            """,
        )

        time_columns, time_rows = run_query(
            connection,
            """
            SELECT FLOOR(TransactionDT / 86400) AS day_bucket,
              COUNT(*) AS tx_count,
              ROUND(
                100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                2
              ) AS fraud_rate_pct
            FROM train_transaction
            GROUP BY day_bucket
            ORDER BY day_bucket
            LIMIT 15
            """,
        )

        return [
            {
                "title": "1. Quick data overview",
                "notes": build_notes(
                    "Start with table size, rough amount metrics, and the number of customer proxies.",
                    f"train_transaction has {transaction_columns} columns, and train_identity has {identity_columns} columns.",
                    "This is the first orientation step before fraud-specific cuts.",
                ),
                "outputs": [
                    {"kind": "html", "content": render_html_table(overview_columns, overview_rows, displayed_rows=10)},
                ],
            },
            {
                "title": "2. Target and class imbalance",
                "notes": build_notes(
                    "For anti-fraud, this is a mandatory early check because fraud is usually rare.",
                    "This block explains why threshold tuning and review load matter later in the project.",
                ),
                "outputs": [
                    {"kind": "html", "content": render_html_table(imbalance_columns, imbalance_rows, displayed_rows=10)},
                    {
                        "kind": "image",
                        "content": render_chart(
                            ["non_fraud", "fraud"],
                            [float(imbalance_rows[0][2]), float(imbalance_rows[0][1])],
                            "Class imbalance in train_transaction",
                            color="#dc2626",
                        ),
                    },
                ],
            },
            {
                "title": "3. Missing values in key columns",
                "notes": build_notes(
                    "Look only at the fields that matter for the first anti-fraud pass.",
                    "This block helps decide which columns are interpretable and safe for the first feature set.",
                ),
                "outputs": [
                    {"kind": "html", "content": render_html_table(missing_columns, missing_rows, displayed_rows=12)},
                ],
            },
            {
                "title": "4. Transaction amount patterns",
                "notes": build_notes(
                    "TransactionAmt is one of the first useful numerical signals in fraud analysis.",
                    "Instead of plotting every raw row, the UI shows compact bucket-level patterns and fraud rate.",
                ),
                "outputs": [
                    {"kind": "html", "content": render_html_table(amount_bucket_columns, amount_bucket_rows, displayed_rows=10)},
                    {
                        "kind": "image",
                        "content": render_chart(
                            [str(row[0]) for row in amount_bucket_rows],
                            [float(row[2]) for row in amount_bucket_rows],
                            "Fraud rate by transaction amount bucket",
                        ),
                    },
                ],
            },
            {
                "title": "5. Product segment patterns",
                "notes": build_notes(
                    "This block shows which product segments stand out before any model is trained.",
                    "ProductCD later becomes part of both anti-fraud hypotheses and MVP features.",
                ),
                "outputs": [
                    {"kind": "html", "content": render_html_table(product_columns, product_rows, displayed_rows=10)},
                    {
                        "kind": "image",
                        "content": render_chart(
                            [str(row[0]) for row in product_rows],
                            [float(row[2]) for row in product_rows],
                            "Fraud rate by ProductCD",
                        ),
                    },
                ],
            },
            {
                "title": "6. Time-based fraud pattern preview",
                "notes": build_notes(
                    "TransactionDT is relative time, not a calendar timestamp, so the first pass uses coarse buckets.",
                    "This helps explain why temporal reasoning matters in later SQL and feature engineering.",
                ),
                "outputs": [
                    {"kind": "html", "content": render_html_table(time_columns, time_rows, displayed_rows=15)},
                    {
                        "kind": "image",
                        "content": render_chart(
                            [str(int(row[0])) for row in time_rows],
                            [float(row[2]) for row in time_rows],
                            "Fraud rate by relative day bucket",
                            color="#7c3aed",
                        ),
                    },
                ],
            },
        ]
    finally:
        connection.close()
