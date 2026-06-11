from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import requests


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_PAYLOAD = {
    "transaction_id": 1000001,
    "transaction_amount": 550,
    "product_cd": "W",
    "card1": 13926,
    "card4": "discover",
    "card6": "credit",
    "p_emaildomain": "outlook.com",
    "r_emaildomain": "gmail.com",
}


def load_payload(payload_file: str | None) -> dict[str, Any]:
    if payload_file is None:
        return DEFAULT_PAYLOAD.copy()

    payload_path = Path(payload_file)

    if not payload_path.exists():
        raise FileNotFoundError(f"Payload file was not found: {payload_path}")

    with payload_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a single transaction payload to the local /score endpoint."
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"API base URL. Default: {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--payload-file",
        default=None,
        help="Optional path to a JSON file with a custom /score request body.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds. Default: 10",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = load_payload(args.payload_file)
    score_url = f"{args.base_url.rstrip('/')}/score"

    response = requests.post(score_url, json=payload, timeout=args.timeout)
    response.raise_for_status()

    print("Request payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print()
    print("Response:")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
