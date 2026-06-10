#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import duckdb


def format_table(columns: list[str], rows: list[tuple]) -> str:
    text_rows = [[("" if value is None else str(value)) for value in row] for row in rows]
    widths = [len(column) for column in columns]

    for row in text_rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    header = " | ".join(column.ljust(widths[index]) for index, column in enumerate(columns))
    separator = "-+-".join("-" * widths[index] for index in range(len(columns)))
    body = "\n".join(
        " | ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in text_rows
    )

    if not body:
        return "\n".join([header, separator, "(0 rows)"])

    return "\n".join([header, separator, body, f"({len(rows)} rows)"])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a DuckDB SQL file using the project's Python environment."
    )
    parser.add_argument("sql_file", help="Path to the .sql file to execute")
    parser.add_argument(
        "--db",
        default="ieee_cis.duckdb",
        help="DuckDB database file path. Default: ieee_cis.duckdb",
    )
    args = parser.parse_args()

    project_root = Path.cwd()
    sql_path = (project_root / args.sql_file).resolve() if not Path(args.sql_file).is_absolute() else Path(args.sql_file)
    db_path = (project_root / args.db).resolve() if not Path(args.db).is_absolute() else Path(args.db)

    if not sql_path.exists():
        print(f"SQL file not found: {sql_path}", file=sys.stderr)
        return 1

    sql_text = sql_path.read_text(encoding="utf-8")
    connection = duckdb.connect(str(db_path))

    try:
        result = connection.execute(sql_text)

        if result.description is None:
            print("SQL выполнен, но последний оператор не вернул таблицу.")
            return 0

        columns = [column[0] for column in result.description]
        rows = result.fetchall()
        print(format_table(columns, rows))
        return 0
    except Exception as exc:
        print(f"DuckDB error: {exc}", file=sys.stderr)
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
