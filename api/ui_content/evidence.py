from __future__ import annotations

from pathlib import Path

from api.schemas import ScoreRequest
from api.ui_content.shared import build_duckdb_connection, render_html_table, resolve_dataset_dir, run_query


def _sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _format_pct(value: object) -> str:
    return f"{value}%"


def _build_product_evidence(connection, score_request: ScoreRequest) -> dict[str, object]:
    current_product = score_request.product_cd.strip().upper()
    safe_product = _sql_literal(current_product)

    columns, rows = run_query(
        connection,
        f"""
        SELECT ProductCD,
          COUNT(*) AS tx_count,
          SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) AS fraud_tx_count,
          ROUND(
            100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
            2
          ) AS fraud_rate_pct
        FROM train_transaction
        GROUP BY ProductCD
        ORDER BY CASE WHEN ProductCD = '{safe_product}' THEN 0 ELSE 1 END,
          fraud_rate_pct DESC,
          tx_count DESC
        LIMIT 10
        """,
    )
    _, overall_rows = run_query(
        connection,
        """
        SELECT ROUND(
          100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
          2
        ) AS overall_fraud_rate_pct
        FROM train_transaction
        """,
    )
    current_row = rows[0] if rows else (current_product, 0, 0, 0.0)
    overall_rate = overall_rows[0][0]

    return {
        "title": "ProductCD evidence",
        "intro": (
            f"The current request uses ProductCD={current_product}. "
            "The table below shows how this segment behaves against the rest of the dataset."
        ),
        "summary_items": [
            {"label": "Current ProductCD", "value": current_product},
            {"label": "Segment Fraud Rate", "value": _format_pct(current_row[3])},
            {"label": "Portfolio Fraud Rate", "value": _format_pct(overall_rate)},
            {"label": "Segment Volume", "value": f"{int(current_row[1]):,}"},
        ],
        "result_html": render_html_table(columns, rows, displayed_rows=10),
        "business_note": (
            "If the current product segment runs above the portfolio baseline, "
            "it becomes a readable pre-model risk signal for analysts."
        ),
    }


def _build_email_evidence(
    connection,
    field_name: str,
    field_label: str,
    field_value: str | None,
) -> dict[str, object]:
    current_domain = (field_value or "missing").strip().lower() or "missing"
    safe_domain = _sql_literal(current_domain)

    columns, rows = run_query(
        connection,
        f"""
        SELECT COALESCE(LOWER({field_name}), 'missing') AS email_domain,
          COUNT(*) AS tx_count,
          SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) AS fraud_tx_count,
          ROUND(
            100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
            2
          ) AS fraud_rate_pct
        FROM train_transaction
        GROUP BY email_domain
        ORDER BY CASE WHEN email_domain = '{safe_domain}' THEN 0 ELSE 1 END,
          fraud_rate_pct DESC,
          tx_count DESC
        LIMIT 12
        """,
    )
    _, overall_rows = run_query(
        connection,
        """
        SELECT ROUND(
          100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
          2
        ) AS overall_fraud_rate_pct
        FROM train_transaction
        """,
    )
    current_row = rows[0] if rows else (current_domain, 0, 0, 0.0)
    overall_rate = overall_rows[0][0]

    return {
        "title": f"{field_label} evidence",
        "intro": (
            f"The current request uses {field_name}={current_domain}. "
            "The table shows whether this domain stands above the portfolio baseline."
        ),
        "summary_items": [
            {"label": "Current Domain", "value": current_domain},
            {"label": "Domain Fraud Rate", "value": _format_pct(current_row[3])},
            {"label": "Portfolio Fraud Rate", "value": _format_pct(overall_rate)},
            {"label": "Domain Volume", "value": f"{int(current_row[1]):,}"},
        ],
        "result_html": render_html_table(columns, rows, displayed_rows=12),
        "business_note": (
            "Domain-level cuts are useful because they are readable for both "
            "analysts and business stakeholders and can become lightweight watchlists."
        ),
    }


def _build_amount_evidence(connection, score_request: ScoreRequest) -> dict[str, object]:
    columns, rows = run_query(
        connection,
        f"""
        WITH customer_stats AS (
          SELECT card1 AS customer_proxy,
            COUNT(*) AS tx_count,
            ROUND(AVG(TransactionAmt), 2) AS avg_amount,
            ROUND(COALESCE(STDDEV_SAMP(TransactionAmt), 0), 2) AS std_amount,
            ROUND(AVG(TransactionAmt) + 3 * COALESCE(STDDEV_SAMP(TransactionAmt), 0), 2) AS threshold_amount,
            ROUND(MAX(TransactionAmt), 2) AS max_historical_amount
          FROM train_transaction
          GROUP BY card1
        )
        SELECT customer_proxy,
          tx_count,
          avg_amount,
          std_amount,
          threshold_amount,
          max_historical_amount
        FROM customer_stats
        WHERE customer_proxy = {score_request.card1}
        """,
    )

    if rows:
        baseline_row = rows[0]
        threshold_amount = baseline_row[4]
        result_rows = [
            (
                baseline_row[0],
                score_request.transaction_amount,
                baseline_row[1],
                baseline_row[2],
                baseline_row[3],
                threshold_amount,
                baseline_row[5],
                score_request.transaction_amount > float(threshold_amount),
            )
        ]
    else:
        threshold_amount = "n/a"
        result_rows = [
            (
                score_request.card1,
                score_request.transaction_amount,
                0,
                "n/a",
                "n/a",
                "n/a",
                "n/a",
                False,
            )
        ]

    return {
        "title": "Transaction amount evidence",
        "intro": (
            f"The current request uses card1={score_request.card1} with "
            f"TransactionAmt={score_request.transaction_amount}. "
            "This block compares the amount with the historical baseline for the same customer proxy."
        ),
        "summary_items": [
            {"label": "card1", "value": str(score_request.card1)},
            {"label": "Current Amount", "value": str(score_request.transaction_amount)},
            {"label": "Threshold", "value": str(threshold_amount)},
        ],
        "result_html": render_html_table(
            [
                "customer_proxy",
                "current_amount",
                "tx_count",
                "avg_amount",
                "std_amount",
                "threshold_amount",
                "max_historical_amount",
                "above_threshold",
            ],
            result_rows,
            displayed_rows=1,
        ),
        "business_note": (
            "Customer-relative amount spikes are easier to justify operationally "
            "than raw absolute amount rules, which makes them good manual-review signals."
        ),
    }


def load_score_evidence(
    data_dir: str,
    score_request: ScoreRequest,
    feature_values: dict[str, float],
) -> list[dict[str, object]]:
    base_data_path = Path(data_dir)
    dataset_dir = resolve_dataset_dir(base_data_path)
    if dataset_dir is None:
        return []

    connection = build_duckdb_connection(dataset_dir)
    evidence_blocks: list[dict[str, object]] = []

    try:
        if feature_values.get("feat_productcd_c_flag", 0.0) >= 1.0:
            evidence_blocks.append(_build_product_evidence(connection, score_request))

        if (
            feature_values.get("feat_high_risk_r_email_flag", 0.0) >= 1.0
            or feature_values.get("feat_missing_r_email_flag", 0.0) >= 1.0
        ):
            evidence_blocks.append(
                _build_email_evidence(
                    connection,
                    field_name="R_emaildomain",
                    field_label="Recipient email domain",
                    field_value=score_request.r_emaildomain,
                )
            )

        if feature_values.get("feat_high_risk_p_email_flag", 0.0) >= 1.0:
            evidence_blocks.append(
                _build_email_evidence(
                    connection,
                    field_name="P_emaildomain",
                    field_label="Purchaser email domain",
                    field_value=score_request.p_emaildomain,
                )
            )

        if feature_values.get("feat_amount_gt_card1_avg_plus_3std", 0.0) >= 1.0:
            evidence_blocks.append(_build_amount_evidence(connection, score_request))
    finally:
        connection.close()

    return evidence_blocks
