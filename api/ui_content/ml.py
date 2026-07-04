from __future__ import annotations

import json
from pathlib import Path

from api.i18n import Language, translate


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


def _build_ml_content(
    notebook_path: str,
    named_tables: dict[str, str],
    lang: Language,
    warning: str | None = None,
) -> dict[str, object]:
    tr = lambda uk, en: translate(lang, uk, en)
    content: dict[str, object] = {
        "source_notebook": Path(notebook_path).name,
        "overview_cards": [
            {
                "label": tr("Обрана MVP-модель", "Selected MVP model"),
                "value": "RandomForestClassifier",
                "description": tr(
                    "Поточний найбільш придатний кандидат для демонстраційного скорингу.",
                    "The current best-fit candidate for demo scoring.",
                ),
            },
            {
                "label": tr("Референсна модель", "Reference model"),
                "value": "LogisticRegression",
                "description": tr(
                    "Базова модель, яку збережено для чесного порівняння.",
                    "The baseline model kept for a fair comparison.",
                ),
            },
            {
                "label": tr("Поріг перевірки", "Review threshold"),
                "value": "0.7",
                "description": tr(
                    "Найреалістичніший поточний кандидат для сценарію ручної перевірки.",
                    "The most realistic current candidate for the manual review scenario.",
                ),
            },
            {
                "label": tr("Робочий артефакт", "Serving artifact"),
                "value": tr("Лише RandomForest", "RandomForest only"),
                "description": tr(
                    "Поточний артефакт API-скорингу - це MVP-набір на RandomForest.",
                    "The current API scoring artifact is an MVP bundle built on RandomForest.",
                ),
            },
        ],
        "winner_note": tr(
            "Проєкт залишає RandomForestClassifier як поточну MVP-модель, "
            "тому що вона покращила precision, recall, f1 і roc_auc та водночас "
            "забезпечила нижче навантаження на ручну перевірку на тих самих порогах.",
            "The project keeps RandomForestClassifier as the current MVP model "
            "because it improved precision, recall, f1, and roc_auc while also "
            "delivering lower manual review load at the same thresholds.",
        ),
        "tables": [
            {
                "title": tr("Метрики моделей", "Model metrics"),
                "description": tr(
                    "Ключові валідаційні метрики для двох навчених моделей на "
                    "одному й тому самому feature set та одному validation split.",
                    "Key validation metrics for two trained models on the same "
                    "feature set and the same validation split.",
                ),
                "table_name": "model_metrics_df",
                "html": named_tables.get("model_metrics_df"),
            },
            {
                "title": tr("Дельта метрик", "Metric delta"),
                "description": tr(
                    "Прямий зріз дельти, який робить uplift RandomForest над "
                    "LogisticRegression простим для пояснення.",
                    "A direct delta view that makes the RandomForest uplift over "
                    "LogisticRegression easy to explain.",
                ),
                "table_name": "model_metrics_comparison_df",
                "html": named_tables.get("model_metrics_comparison_df"),
            },
            {
                "title": tr("Порівняння порогів", "Threshold comparison"),
                "description": tr(
                    "Поведінка обох моделей на різних порогах, включно з "
                    "precision, recall, f1, fraud count і manual review rate.",
                    "Behavior of both models at different thresholds, including "
                    "precision, recall, f1, fraud count, and manual review rate.",
                ),
                "table_name": "threshold_df_by_model",
                "html": named_tables.get("threshold_df_by_model"),
            },
            {
                "title": tr("Навантаження ручної перевірки", "Manual review load"),
                "description": tr(
                    "Фокусне порівняння manual review rate за порогами для "
                    "кожної моделі та дельти між ними.",
                    "A focused comparison of manual review rate by threshold for "
                    "each model and the delta between them.",
                ),
                "table_name": "manual_review_comparison_df",
                "html": named_tables.get("manual_review_comparison_df"),
            },
        ],
    }
    if warning:
        content["warning"] = warning
    return content


def load_ml_content(notebook_path: str, lang: Language) -> dict[str, object]:
    notebook_file = Path(notebook_path)
    try:
        notebook = json.loads(notebook_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _build_ml_content(
            notebook_path,
            {},
            lang=lang,
            warning=(
                translate(
                    lang,
                    "Ноутбук із результатами ML недоступний у поточному середовищі. "
                    "Перезберіть контейнер, щоб додати файл 05_model_comparison.ipynb.",
                    "The notebook with ML results is unavailable in the current environment. "
                    "Rebuild the container to add 05_model_comparison.ipynb.",
                )
            ),
        )

    cells = notebook.get("cells", [])
    if not isinstance(cells, list):
        cells = []

    named_tables = _extract_named_table_outputs(cells)
    return _build_ml_content(notebook_path, named_tables, lang=lang)
