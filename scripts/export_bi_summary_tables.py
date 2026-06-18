from __future__ import annotations

import csv
import json
import sys
from html.parser import HTMLParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.ui_content.shared import build_duckdb_connection, resolve_dataset_dir, run_query


class HTMLTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_row = False
        self.in_cell = False
        self.current_cell_parts: list[str] = []
        self.current_row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self.in_row = True
            self.current_row = []
        elif tag in {"th", "td"} and self.in_row:
            self.in_cell = True
            self.current_cell_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"th", "td"} and self.in_cell:
            cell_text = " ".join(part.strip() for part in self.current_cell_parts if part.strip())
            self.current_row.append(cell_text)
            self.in_cell = False
            self.current_cell_parts = []
        elif tag == "tr" and self.in_row:
            if self.current_row:
                self.rows.append(self.current_row)
            self.in_row = False
            self.current_row = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.current_cell_parts.append(data)


def write_csv(output_path: Path, columns: list[str], rows: list[tuple]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        writer.writerows(rows)


def export_duckdb_table(output_path: Path, query: str) -> None:
    data_dir = PROJECT_ROOT / "data"
    dataset_dir = resolve_dataset_dir(data_dir)
    if dataset_dir is None:
        raise FileNotFoundError(
            "Place train_transaction.csv and train_identity.csv into data/raw/ to export BI summary tables."
        )

    connection = build_duckdb_connection(dataset_dir)
    try:
        columns, rows = run_query(connection, query)
    finally:
        connection.close()

    write_csv(output_path, columns, rows)


def export_notebook_html_table(notebook_path: Path, table_name: str, output_path: Path) -> None:
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    cells = notebook.get("cells", [])
    if not isinstance(cells, list):
        cells = []

    target_html = None
    for cell in cells:
        if cell.get("cell_type") != "code":
            continue

        outputs = cell.get("outputs", [])
        if not isinstance(outputs, list):
            continue

        for index, output in enumerate(outputs[:-1]):
            if not isinstance(output, dict):
                continue

            data = output.get("data", {})
            if not isinstance(data, dict):
                continue

            markdown_values = data.get("text/markdown")
            if isinstance(markdown_values, list):
                markdown_title = "".join(str(item) for item in markdown_values).strip()
            else:
                markdown_title = str(markdown_values or "").strip()

            if markdown_title != f"### {table_name}":
                continue

            next_output = outputs[index + 1]
            if not isinstance(next_output, dict):
                continue

            next_data = next_output.get("data", {})
            if not isinstance(next_data, dict):
                continue

            html_values = next_data.get("text/html")
            if isinstance(html_values, list):
                target_html = "".join(str(item) for item in html_values).strip()
            else:
                target_html = str(html_values or "").strip()
            break

        if target_html:
            break

    if not target_html:
        raise ValueError(f"Could not find notebook table: {table_name}")

    parser = HTMLTableParser()
    parser.feed(target_html)
    if not parser.rows:
        raise ValueError(f"Could not parse notebook table HTML: {table_name}")

    columns = parser.rows[0]
    rows = [row for row in parser.rows[1:] if len(row) == len(columns)]

    # Jupyter HTML tables often include an unnamed index column as the first field.
    if columns and columns[0] == "":
        columns = columns[1:]
        rows = [row[1:] for row in rows]

    rows_as_tuples = [tuple(row) for row in rows]
    write_csv(output_path, columns, rows_as_tuples)


def main() -> None:
    output_dir = PROJECT_ROOT / "data" / "bi_exports"
    notebook_path = PROJECT_ROOT / "notebooks" / "05_model_comparison.ipynb"

    export_duckdb_table(
        output_dir / "fraud_overview.csv",
        """
        SELECT COUNT(*) AS total_transactions,
          SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) AS fraud_transactions,
          ROUND(
            100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
            4
          ) AS fraud_rate_pct,
          ROUND(AVG(TransactionAmt), 2) AS avg_transaction_amount,
          COUNT(DISTINCT card1) AS customer_proxy_count
        FROM train_transaction
        """,
    )
    export_duckdb_table(
        output_dir / "risk_segmentation.csv",
        """
        SELECT ProductCD AS segment_value,
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
    export_duckdb_table(
        output_dir / "top_suspicious_patterns.csv",
        """
        WITH product_patterns AS (
          SELECT 'ProductCD' AS pattern_type,
            ProductCD AS pattern_value,
            COUNT(*) AS tx_count,
            ROUND(
              100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
              2
            ) AS fraud_rate_pct
          FROM train_transaction
          GROUP BY ProductCD
        ),
        recipient_email_patterns AS (
          SELECT 'R_emaildomain' AS pattern_type,
            COALESCE(R_emaildomain, 'missing') AS pattern_value,
            COUNT(*) AS tx_count,
            ROUND(
              100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
              2
            ) AS fraud_rate_pct
          FROM train_transaction
          GROUP BY pattern_value
          HAVING COUNT(*) >= 100
        ),
        purchaser_email_patterns AS (
          SELECT 'P_emaildomain' AS pattern_type,
            COALESCE(P_emaildomain, 'missing') AS pattern_value,
            COUNT(*) AS tx_count,
            ROUND(
              100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
              2
            ) AS fraud_rate_pct
          FROM train_transaction
          GROUP BY pattern_value
          HAVING COUNT(*) >= 100
        )
        SELECT *
        FROM (
          SELECT * FROM product_patterns
          UNION ALL
          SELECT * FROM recipient_email_patterns
          UNION ALL
          SELECT * FROM purchaser_email_patterns
        )
        ORDER BY fraud_rate_pct DESC, tx_count DESC
        LIMIT 20
        """,
    )
    export_duckdb_table(
        output_dir / "sql_investigation_highlights.csv",
        """
        WITH customer_stats AS (
          SELECT card1 AS customer_proxy,
            AVG(TransactionAmt) AS avg_amount,
            STDDEV_SAMP(TransactionAmt) AS std_amount
          FROM train_transaction
          GROUP BY card1
        )
        SELECT t.TransactionID,
          t.card1 AS customer_proxy,
          ROUND(t.TransactionAmt, 2) AS transaction_amount,
          ROUND(s.avg_amount, 2) AS avg_amount,
          ROUND(COALESCE(s.std_amount, 0), 2) AS std_amount,
          ROUND(s.avg_amount + 3 * COALESCE(s.std_amount, 0), 2) AS threshold_amount
        FROM train_transaction t
          JOIN customer_stats s ON t.card1 = s.customer_proxy
        WHERE t.TransactionAmt > s.avg_amount + 3 * COALESCE(s.std_amount, 0)
        ORDER BY t.TransactionAmt DESC
        LIMIT 20
        """,
    )

    export_notebook_html_table(
        notebook_path,
        "model_metrics_df",
        output_path=output_dir / "ml_model_metrics.csv",
    )
    export_notebook_html_table(
        notebook_path,
        "threshold_df_by_model",
        output_path=output_dir / "ml_threshold_comparison.csv",
    )
    export_notebook_html_table(
        notebook_path,
        "manual_review_comparison_df",
        output_path=output_dir / "ml_manual_review_comparison.csv",
    )

    print(f"BI summary tables exported to {output_dir}")


if __name__ == "__main__":
    main()
