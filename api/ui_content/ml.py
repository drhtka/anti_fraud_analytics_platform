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


def load_ml_content(notebook_path: str) -> dict[str, object]:
    notebook = json.loads(Path(notebook_path).read_text(encoding="utf-8"))
    cells = notebook.get("cells", [])
    if not isinstance(cells, list):
        cells = []

    named_tables = _extract_named_table_outputs(cells)

    return {
        "source_notebook": Path(notebook_path).name,
        "overview_cards": [
            {
                "label": "Обрана MVP-модель",
                "value": "RandomForestClassifier",
                "description": "Поточний найбільш придатний кандидат для демонстраційного скорингу.",
            },
            {
                "label": "Референсна модель",
                "value": "LogisticRegression",
                "description": "Базова модель, яку збережено для чесного порівняння.",
            },
            {
                "label": "Поріг перевірки",
                "value": "0.7",
                "description": "Найреалістичніший поточний кандидат для сценарію ручної перевірки.",
            },
            {
                "label": "Робочий артефакт",
                "value": "Лише RandomForest",
                "description": "Поточний артефакт API-скорингу - це MVP-набір на RandomForest.",
            },
        ],
        "winner_note": (
            "Проєкт залишає RandomForestClassifier як поточну MVP-модель, "
            "тому що вона покращила precision, recall, f1 і roc_auc та водночас "
            "забезпечила нижче навантаження на ручну перевірку на тих самих порогах."
        ),
        "tables": [
            {
                "title": "Метрики моделей",
                "description": (
                    "Ключові валідаційні метрики для двох навчених моделей на "
                    "одному й тому самому feature set та одному validation split."
                ),
                "table_name": "model_metrics_df",
                "html": named_tables.get("model_metrics_df"),
            },
            {
                "title": "Дельта метрик",
                "description": (
                    "Прямий зріз дельти, який робить uplift RandomForest над "
                    "LogisticRegression простим для пояснення."
                ),
                "table_name": "model_metrics_comparison_df",
                "html": named_tables.get("model_metrics_comparison_df"),
            },
            {
                "title": "Порівняння порогів",
                "description": (
                    "Поведінка обох моделей на різних порогах, включно з "
                    "precision, recall, f1, fraud count і manual review rate."
                ),
                "table_name": "threshold_df_by_model",
                "html": named_tables.get("threshold_df_by_model"),
            },
            {
                "title": "Навантаження ручної перевірки",
                "description": (
                    "Фокусне порівняння manual review rate за порогами для "
                    "кожної моделі та дельти між ними."
                ),
                "table_name": "manual_review_comparison_df",
                "html": named_tables.get("manual_review_comparison_df"),
            },
        ],
    }
