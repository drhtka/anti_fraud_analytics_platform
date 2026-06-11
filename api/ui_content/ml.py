from __future__ import annotations

import json
from pathlib import Path


def _join_notebook_value(value: object) -> str:
    if isinstance(value, list):
        return "".join(str(item) for item in value)
    if isinstance(value, str):
        return value
    return ""


def _extract_named_table_outputs(cells: list[dict[str, object]]) -> dict[str, str]:
    named_tables: dict[str, str] = {}

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

            markdown_title = _join_notebook_value(data.get("text/markdown")).strip()
            if not markdown_title.startswith("### "):
                continue

            table_name = markdown_title.removeprefix("### ").strip()
            next_output = outputs[index + 1]
            if not isinstance(next_output, dict):
                continue

            next_data = next_output.get("data", {})
            if not isinstance(next_data, dict):
                continue

            html_table = _join_notebook_value(next_data.get("text/html")).strip()
            if html_table:
                named_tables[table_name] = html_table

    return named_tables


def _extract_week3_summary(cells: list[dict[str, object]]) -> list[str]:
    for cell in cells:
        if cell.get("cell_type") != "markdown":
            continue

        source = _join_notebook_value(cell.get("source"))
        if "## Week 3 Final Summary" not in source:
            continue

        summary_lines: list[str] = []
        for raw_line in source.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("## "):
                continue
            summary_lines.append(line.removeprefix("- ").strip())
        return summary_lines

    return []


def load_ml_content(notebook_path: str) -> dict[str, object]:
    notebook = json.loads(Path(notebook_path).read_text(encoding="utf-8"))
    cells = notebook.get("cells", [])
    if not isinstance(cells, list):
        cells = []

    named_tables = _extract_named_table_outputs(cells)
    final_summary = _extract_week3_summary(cells)

    return {
        "source_notebook": Path(notebook_path).name,
        "overview_cards": [
            {
                "label": "Selected MVP Model",
                "value": "RandomForestClassifier",
                "description": "Current production-like candidate for the scoring demo.",
            },
            {
                "label": "Reference Model",
                "value": "LogisticRegression",
                "description": "Baseline kept for honest comparison during Week 3.",
            },
            {
                "label": "Review Threshold",
                "value": "0.7",
                "description": "Most realistic current candidate for manual review flow.",
            },
            {
                "label": "Live Artifact",
                "value": "RandomForest only",
                "description": "The current API scoring artifact is the RandomForest MVP bundle.",
            },
        ],
        "winner_note": (
            "The project keeps RandomForestClassifier as the current MVP model "
            "because it improved precision, recall, f1, and roc_auc while also "
            "keeping manual review load lower at the same thresholds."
        ),
        "final_summary": final_summary,
        "tables": [
            {
                "title": "Model Metrics",
                "description": (
                    "The core validation metrics for the two trained models on "
                    "the same feature set and the same validation split."
                ),
                "table_name": "model_metrics_df",
                "html": named_tables.get("model_metrics_df"),
            },
            {
                "title": "Metric Delta",
                "description": (
                    "A direct delta view that makes the RandomForest uplift over "
                    "LogisticRegression easy to explain."
                ),
                "table_name": "model_metrics_comparison_df",
                "html": named_tables.get("model_metrics_comparison_df"),
            },
            {
                "title": "Threshold Comparison",
                "description": (
                    "Threshold-by-threshold behavior for both models, including "
                    "precision, recall, f1, fraud count, and manual review rate."
                ),
                "table_name": "threshold_df_by_model",
                "html": named_tables.get("threshold_df_by_model"),
            },
            {
                "title": "Manual Review Load",
                "description": (
                    "A focused comparison of manual review rate by threshold for "
                    "each model and the delta between them."
                ),
                "table_name": "manual_review_comparison_df",
                "html": named_tables.get("manual_review_comparison_df"),
            },
        ],
    }
