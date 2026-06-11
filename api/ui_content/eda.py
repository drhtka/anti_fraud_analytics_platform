from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from api.ui_content.shared import (
    build_duckdb_connection,
    build_notes,
    render_chart,
    render_html_table,
    resolve_dataset_dir,
    run_query,
)


@lru_cache(maxsize=1)
def load_eda_sections(data_dir: str) -> list[dict[str, object]]:
    base_data_path = Path(data_dir)
    dataset_dir = resolve_dataset_dir(base_data_path)
    if dataset_dir is None:
        return [
            {
                "title": "EDA data is unavailable",
                "notes": build_notes(
                    "Place train_transaction.csv and train_identity.csv into data/raw/ to build the EDA screen.",
                    "As a fallback, the app also supports the same files directly in data/.",
                    "The EDA UI is designed to read directly from local CSV files instead of notebook outputs.",
                ),
                "outputs": [],
            }
        ]

    connection = build_duckdb_connection(dataset_dir)
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

        email_domain_columns, email_domain_rows = run_query(
            connection,
            """
            SELECT COALESCE(R_emaildomain, 'missing') AS recipient_email_domain,
              COUNT(*) AS tx_count,
              ROUND(
                100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                2
              ) AS fraud_rate_pct
            FROM train_transaction
            GROUP BY recipient_email_domain
            HAVING COUNT(*) >= 100
            ORDER BY fraud_rate_pct DESC, tx_count DESC
            LIMIT 12
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

        return [
            {
                "title": "1. Quick data overview",
                "table_name": "eda_dataset_overview",
                "description": "A first orientation block with dataset size, amount scale, and customer-proxy coverage.",
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
                "table_name": "eda_target_imbalance",
                "description": "A compact view of fraud rarity that explains why anti-fraud evaluation cannot rely on accuracy alone.",
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
                "title": "3. Product segment patterns",
                "table_name": "eda_product_segment_risk",
                "description": "A segment-level table that shows which ProductCD groups look riskier before any model is trained.",
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
                "title": "4. Recipient email domain patterns",
                "table_name": "eda_recipient_email_domain_risk",
                "description": "A domain-level cut that helps explain why some recipient domains became strong suspicious signals.",
                "notes": build_notes(
                    "Email domain analysis is useful because it is readable both for analysts and for business stakeholders.",
                    "This block also links directly to later rule ideas and MVP scoring signals.",
                ),
                "outputs": [
                    {"kind": "html", "content": render_html_table(email_domain_columns, email_domain_rows, displayed_rows=12)},
                    {
                        "kind": "image",
                        "content": render_chart(
                            [str(row[0]) for row in email_domain_rows[:8]],
                            [float(row[2]) for row in email_domain_rows[:8]],
                            "Fraud rate by recipient email domain",
                            color="#7c3aed",
                        ),
                    },
                ],
            },
        ]
    finally:
        connection.close()
