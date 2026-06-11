from __future__ import annotations

import json
from functools import lru_cache
from html import escape
from pathlib import Path

import duckdb


def _normalize_output_text(value: str | list[str] | None) -> str:
    if value is None:
        return ""
    return "".join(value) if isinstance(value, list) else value


def _parse_markdown_notes(markdown_text: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in markdown_text.splitlines()[1:] if line.strip()]
    notes: list[dict[str, str]] = []

    for line in lines:
        if line.startswith("- "):
            notes.append({"kind": "bullet", "text": line[2:]})
        elif line[:2].isdigit() and line[1:3] == ". ":
            notes.append({"kind": "bullet", "text": line[3:]})
        else:
            notes.append({"kind": "paragraph", "text": line})

    return notes


def _parse_notebook_output(output: dict[str, object]) -> dict[str, str] | None:
    output_type = output.get("output_type")

    if output_type == "stream":
        text = _normalize_output_text(output.get("text"))  # type: ignore[arg-type]
        return {"kind": "text", "content": text.strip()} if text.strip() else None

    data = output.get("data", {})
    if not isinstance(data, dict):
        return None

    if "image/png" in data:
        return {"kind": "image", "content": f"data:image/png;base64,{data['image/png']}"}

    if "text/html" in data:
        html_content = _normalize_output_text(data["text/html"])  # type: ignore[arg-type]
        return {"kind": "html", "content": html_content}

    if "text/plain" in data:
        text_content = _normalize_output_text(data["text/plain"])  # type: ignore[arg-type]
        return {"kind": "text", "content": text_content}

    return None


@lru_cache(maxsize=1)
def load_eda_sections(notebook_path: str) -> list[dict[str, object]]:
    notebook = json.loads(Path(notebook_path).read_text(encoding="utf-8"))
    cells = notebook.get("cells", [])
    sections: list[dict[str, object]] = []
    current_section: dict[str, object] | None = None

    for cell in cells:
        cell_type = cell.get("cell_type")
        source = "".join(cell.get("source", []))
        stripped = source.strip()

        if cell_type == "markdown" and stripped.startswith("## "):
            if current_section is not None:
                sections.append(current_section)

            title_line = stripped.splitlines()[0]
            current_section = {
                "title": title_line.removeprefix("## ").strip(),
                "notes": _parse_markdown_notes(stripped),
                "outputs": [],
            }
            continue

        if cell_type == "code" and current_section is not None:
            for output in cell.get("outputs", []):
                parsed_output = _parse_notebook_output(output)
                if parsed_output is not None:
                    current_section["outputs"].append(parsed_output)

    if current_section is not None:
        sections.append(current_section)

    return sections


def _render_html_table(columns: list[str], rows: list[tuple], displayed_rows: int) -> str:
    header_html = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body_rows = rows[:displayed_rows]
    body_html = "".join(
        "<tr>"
        + "".join(f"<td>{escape('' if value is None else str(value))}</td>" for value in row)
        + "</tr>"
        for row in body_rows
    )

    if not body_rows:
        body_html = f'<tr><td colspan="{len(columns)}">(0 rows)</td></tr>'

    return (
        '<div class="table-wrapper">'
        '<table class="data-table">'
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{body_html}</tbody>"
        "</table>"
        f'<p class="table-caption">Showing {min(len(rows), displayed_rows)} of {len(rows)} rows.</p>'
        "</div>"
    )


def _build_duckdb_connection(data_dir: Path) -> duckdb.DuckDBPyConnection:
    tx_path = str((data_dir / "train_transaction.csv").resolve()).replace("'", "''")
    identity_path = str((data_dir / "train_identity.csv").resolve()).replace("'", "''")

    connection = duckdb.connect(database=":memory:")
    connection.execute(
        f"""
        CREATE VIEW train_transaction AS
        SELECT *
        FROM read_csv_auto('{tx_path}', header = true)
        """
    )
    connection.execute(
        f"""
        CREATE VIEW train_identity AS
        SELECT *
        FROM read_csv_auto('{identity_path}', header = true)
        """
    )
    connection.execute(
        """
        CREATE VIEW train_tx_identity AS
        SELECT t.*,
          i.DeviceType,
          i.DeviceInfo
        FROM train_transaction t
          LEFT JOIN train_identity i USING (TransactionID)
        """
    )
    return connection


@lru_cache(maxsize=1)
def load_sql_sections(data_dir: str) -> list[dict[str, object]]:
    data_path = Path(data_dir)
    if not (data_path / "train_transaction.csv").exists() or not (data_path / "train_identity.csv").exists():
        return [
            {
                "title": "SQL results are unavailable",
                "table_name": "missing_local_data",
                "source_file": "sql/",
                "description": "The SQL screen needs local IEEE-CIS CSV files in data/ to render result tables.",
                "query": "Place train_transaction.csv and train_identity.csv into data/ to enable live SQL sections.",
                "reading_notes": [
                    "The UI is ready for live DuckDB-backed SQL blocks.",
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
            "title": "3. Fraud rate by card4",
            "table_name": "fraud_rate_by_card4",
            "source_file": "sql/ieee_cis_week_1_duckdb.sql",
            "description": "Card network segmentation helps identify whether some payment channels look riskier than others.",
            "query": """
                SELECT card4,
                  COUNT(*) AS tx_count,
                  SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) AS fraud_tx_count,
                  ROUND(
                    100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                    2
                  ) AS fraud_rate_pct
                FROM train_transaction
                GROUP BY card4
                ORDER BY fraud_rate_pct DESC, tx_count DESC
            """,
            "reading_notes": [
                "Use this table to explain why card network became part of the MVP feature set.",
                "This also supports anti-fraud storytelling in business language.",
            ],
        },
        {
            "title": "4. Fraud rate by recipient email domain",
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
            "title": "5. Large transactions vs customer baseline",
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
        {
            "title": "6. Region changes within one hour",
            "table_name": "rapid_region_changes",
            "source_file": "sql/02_suspicious_patterns.sql",
            "description": "This block catches fast changes in region-like proxy values for the same customer proxy.",
            "query": """
                SELECT customer_proxy,
                  TransactionID,
                  TransactionDT,
                  region_proxy,
                  prev_region,
                  dt_delta_seconds
                FROM (
                    SELECT TransactionID,
                      card1 AS customer_proxy,
                      TransactionDT,
                      addr1 AS region_proxy,
                      LAG(addr1) OVER (
                        PARTITION BY card1
                        ORDER BY TransactionDT
                      ) AS prev_region,
                      TransactionDT - LAG(TransactionDT) OVER (
                        PARTITION BY card1
                        ORDER BY TransactionDT
                      ) AS dt_delta_seconds
                    FROM train_transaction
                  ) region_changes
                WHERE prev_region IS NOT NULL
                  AND region_proxy IS NOT NULL
                  AND prev_region != region_proxy
                  AND dt_delta_seconds <= 3600
                ORDER BY dt_delta_seconds ASC, customer_proxy
                LIMIT 15
            """,
            "reading_notes": [
                "This is a good example of a temporal anti-fraud hypothesis translated into SQL.",
                "It shows how user behavior and short-term inconsistency can become suspicious patterns.",
            ],
        },
    ]

    connection = _build_duckdb_connection(data_path)
    try:
        for section in sql_sections:
            result = connection.execute(section["query"])
            columns = [column[0] for column in result.description]
            rows = result.fetchall()
            section["result_html"] = _render_html_table(columns, rows, displayed_rows=12)
    finally:
        connection.close()

    return sql_sections
