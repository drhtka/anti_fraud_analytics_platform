from __future__ import annotations

import base64
import json
from html import escape
from io import BytesIO
from pathlib import Path

import duckdb
import matplotlib

# FastAPI renders charts on the server, so a non-interactive backend is required.
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA_FILE_NAMES = ("train_transaction.csv", "train_identity.csv")
CACHE_SCHEMA_VERSION = 1


def build_notes(*items: str) -> list[dict[str, str]]:
    return [{"kind": "bullet", "text": item} for item in items]


def render_chart(
    x_values: list[str],
    y_values: list[float],
    title: str,
    color: str = "#2563eb",
) -> str:
    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.bar(x_values, y_values, color=color)
    axis.set_title(title)
    axis.tick_params(axis="x", rotation=30)
    axis.grid(axis="y", linestyle="--", alpha=0.3)
    figure.tight_layout()

    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=120, bbox_inches="tight")
    plt.close(figure)

    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def render_html_table(columns: list[str], rows: list[tuple], displayed_rows: int) -> str:
    header_html = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body_rows = rows[:displayed_rows]
    body_html = "".join(
        "<tr>"
        + "".join(f"<td>{escape('' if value is None else str(value))}</td>" for value in row)
        + "</tr>"
        for row in body_rows
    )

    if not body_rows:
        body_html = f'<tr><td colspan="{len(columns)}">(0 рядків)</td></tr>'

    return (
        '<div class="table-wrapper">'
        '<table class="data-table">'
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{body_html}</tbody>"
        "</table>"
        f'<p class="table-caption">Показано {min(len(rows), displayed_rows)} з {len(rows)} рядків.</p>'
        "</div>"
    )


def run_query(connection: duckdb.DuckDBPyConnection, query: str) -> tuple[list[str], list[tuple]]:
    result = connection.execute(query)
    columns = [column[0] for column in result.description]
    rows = result.fetchall()
    return columns, rows


def resolve_dataset_dir(data_dir: Path) -> Path | None:
    candidate_dirs = [
        data_dir / "raw",
        data_dir,
    ]

    for candidate_dir in candidate_dirs:
        if all((candidate_dir / file_name).exists() for file_name in DATA_FILE_NAMES):
            return candidate_dir

    return None


def get_ui_cache_dir(data_dir: Path) -> Path:
    return data_dir.parent / ".cache" / "ui_content"


def build_dataset_fingerprint(dataset_dir: Path) -> dict[str, object]:
    return {
        "schema_version": CACHE_SCHEMA_VERSION,
        "dataset_dir": str(dataset_dir.resolve()),
        "files": {
            file_name: {
                "size": (dataset_dir / file_name).stat().st_size,
                "mtime_ns": (dataset_dir / file_name).stat().st_mtime_ns,
            }
            for file_name in DATA_FILE_NAMES
        },
    }


def load_cached_payload(data_dir: Path, cache_name: str) -> object | None:
    dataset_dir = resolve_dataset_dir(data_dir)
    if dataset_dir is None:
        return None

    cache_file = get_ui_cache_dir(data_dir) / f"{cache_name}.json"
    if not cache_file.exists():
        return None

    try:
        cached_document = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    expected_fingerprint = build_dataset_fingerprint(dataset_dir)
    if cached_document.get("fingerprint") != expected_fingerprint:
        return None

    return cached_document.get("payload")


def store_cached_payload(data_dir: Path, cache_name: str, payload: object) -> None:
    dataset_dir = resolve_dataset_dir(data_dir)
    if dataset_dir is None:
        return

    cache_dir = get_ui_cache_dir(data_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{cache_name}.json"
    cache_document = {
        "fingerprint": build_dataset_fingerprint(dataset_dir),
        "payload": payload,
    }
    cache_file.write_text(json.dumps(cache_document), encoding="utf-8")


def build_duckdb_connection(data_dir: Path) -> duckdb.DuckDBPyConnection:
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
