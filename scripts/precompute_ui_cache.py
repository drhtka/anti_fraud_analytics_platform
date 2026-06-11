from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.ui_content import load_eda_sections, load_eda_summary, load_sql_sections
from api.ui_content.shared import get_ui_cache_dir


def main() -> None:
    data_dir = PROJECT_ROOT / "data"
    cache_dir = get_ui_cache_dir(data_dir)

    steps = [
        ("eda_summary", load_eda_summary),
        ("eda_sections", load_eda_sections),
        ("sql_sections", load_sql_sections),
    ]

    print(f"Precomputing UI cache from {data_dir}")
    print(f"Cache directory: {cache_dir}")

    for cache_name, loader in steps:
        started_at = perf_counter()
        payload = loader(str(data_dir))
        elapsed = perf_counter() - started_at
        size = len(payload) if isinstance(payload, list) else 0
        print(f"- {cache_name}: {size} items in {elapsed:.2f}s")

    print("UI cache precompute completed.")


if __name__ == "__main__":
    main()
