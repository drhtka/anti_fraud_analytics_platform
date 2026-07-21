from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from api.i18n import Language, translate
from api.schemas import ScoreRequest
from api.ui_content.shared import (
    build_duckdb_connection,
    load_cached_payload,
    render_html_table,
    resolve_dataset_dir,
    run_query,
    store_cached_payload,
)


DEBUG_LANGUAGE_SWITCH_LOG = Path(__file__).resolve().parents[2] / "debug-language-switch-lag.ndjson"


def append_debug_language_switch_log(event: str, payload: dict[str, object]) -> None:
    # region debug-point language-switch-log-helper
    DEBUG_LANGUAGE_SWITCH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DEBUG_LANGUAGE_SWITCH_LOG.open("a", encoding="utf-8") as log_file:
        log_file.write(
            json.dumps(
                {
                    "event": event,
                    "payload": payload,
                    "at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    # endregion debug-point language-switch-log-helper


def _sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _format_pct(value: object) -> str:
    return f"{value}%"


def _build_score_evidence_cache_key(
    score_request: ScoreRequest,
    feature_values: dict[str, float],
    lang: Language,
) -> str:
    raw_payload = json.dumps(
        {
            "request": score_request.model_dump(mode="json"),
            "feature_values": feature_values,
            "lang": lang,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    payload_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
    return f"score_evidence_{payload_hash}"


def _build_score_evidence_raw_cache_key(
    score_request: ScoreRequest,
    feature_values: dict[str, float],
) -> str:
    raw_payload = json.dumps(
        {
            "request": score_request.model_dump(mode="json"),
            "feature_values": feature_values,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    payload_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
    return f"score_evidence_raw_{payload_hash}"


def _build_product_evidence_raw(connection, score_request: ScoreRequest) -> dict[str, object]:
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
    current_row = list(rows[0]) if rows else [current_product, 0, 0, 0.0]
    overall_rate = overall_rows[0][0]

    return {
        "kind": "product",
        "current_product": current_product,
        "columns": columns,
        "rows": [list(row) for row in rows],
        "current_row": current_row,
        "overall_rate": overall_rate,
        "displayed_rows": 10,
    }


def _build_email_evidence_raw(
    connection,
    field_name: str,
    field_value: str | None,
) -> dict[str, object]:
    current_domain_key = (field_value or "missing").strip().lower() or "missing"
    safe_domain = _sql_literal(current_domain_key)

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
    current_row = list(rows[0]) if rows else [current_domain_key, 0, 0, 0.0]
    overall_rate = overall_rows[0][0]

    return {
        "kind": "email",
        "field_name": field_name,
        "current_domain_key": current_domain_key,
        "columns": columns,
        "rows": [list(row) for row in rows],
        "current_row": current_row,
        "overall_rate": overall_rate,
        "displayed_rows": 12,
    }


def _build_amount_evidence_raw(
    connection,
    score_request: ScoreRequest,
) -> dict[str, object]:
    _, rows = run_query(
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
        baseline_row = list(rows[0])
        threshold_amount = baseline_row[4]
        result_rows = [
            [
                baseline_row[0],
                score_request.transaction_amount,
                baseline_row[1],
                baseline_row[2],
                baseline_row[3],
                threshold_amount,
                baseline_row[5],
                score_request.transaction_amount > float(threshold_amount),
            ]
        ]
    else:
        threshold_amount = None
        result_rows = [
            [
                score_request.card1,
                score_request.transaction_amount,
                0,
                None,
                None,
                None,
                None,
                False,
            ]
        ]

    return {
        "kind": "amount",
        "card1": score_request.card1,
        "transaction_amount": score_request.transaction_amount,
        "threshold_amount": threshold_amount,
        "result_rows": result_rows,
        "displayed_rows": 1,
    }


def _localize_evidence_block(raw_block: dict[str, object], lang: Language) -> dict[str, object]:
    tr = lambda uk, en: translate(lang, uk, en)
    kind = raw_block["kind"]

    if kind == "product":
        current_product = str(raw_block["current_product"])
        current_row = raw_block["current_row"]
        overall_rate = raw_block["overall_rate"]
        return {
            "title": tr("Підтвердження по ProductCD", "ProductCD evidence"),
            "intro": tr(
                f"Поточний запит використовує ProductCD={current_product}. "
                "Таблиця нижче показує, як цей сегмент поводиться відносно решти датасету.",
                f"The current request uses ProductCD={current_product}. "
                "The table below shows how this segment behaves relative to the rest of the dataset.",
            ),
            "summary_items": [
                {"label": tr("Поточний ProductCD", "Current ProductCD"), "value": current_product},
                {"label": tr("Рівень фроду сегмента", "Segment fraud rate"), "value": _format_pct(current_row[3])},
                {"label": tr("Рівень фроду портфеля", "Portfolio fraud rate"), "value": _format_pct(overall_rate)},
                {"label": tr("Обсяг сегмента", "Segment volume"), "value": f"{int(current_row[1]):,}"},
            ],
            "result_html": render_html_table(
                raw_block["columns"],
                raw_block["rows"],
                displayed_rows=int(raw_block["displayed_rows"]),
                lang=lang,
            ),
            "business_note": tr(
                "Якщо поточний продуктовий сегмент має показник вище за базовий "
                "рівень портфеля, він стає зрозумілим сигналом ризику для аналітика ще до моделі.",
                "If the current product segment is above the portfolio baseline, it becomes a clear risk signal for the analyst even before the model.",
            ),
        }

    if kind == "email":
        field_name = str(raw_block["field_name"])
        current_domain_key = str(raw_block["current_domain_key"])
        current_row = raw_block["current_row"]
        overall_rate = raw_block["overall_rate"]
        display_domain = (
            tr("відсутній", "missing")
            if current_domain_key == "missing"
            else current_domain_key
        )
        field_label = (
            tr("Домен email отримувача", "Recipient email domain")
            if field_name == "R_emaildomain"
            else tr("Домен email покупця", "Purchaser email domain")
        )
        return {
            "title": tr(f"{field_label}: підтвердження", f"{field_label}: evidence"),
            "intro": tr(
                f"Поточний запит використовує {field_name}={display_domain}. "
                "Таблиця показує, чи перевищує цей домен базовий рівень портфеля.",
                f"The current request uses {field_name}={display_domain}. "
                "The table shows whether this domain is above the portfolio baseline.",
            ),
            "summary_items": [
                {"label": tr("Поточний домен", "Current domain"), "value": display_domain},
                {"label": tr("Рівень фроду домену", "Domain fraud rate"), "value": _format_pct(current_row[3])},
                {"label": tr("Рівень фроду портфеля", "Portfolio fraud rate"), "value": _format_pct(overall_rate)},
                {"label": tr("Обсяг домену", "Domain volume"), "value": f"{int(current_row[1]):,}"},
            ],
            "result_html": render_html_table(
                raw_block["columns"],
                raw_block["rows"],
                displayed_rows=int(raw_block["displayed_rows"]),
                lang=lang,
            ),
            "business_note": tr(
                "Зрізи на рівні доменів корисні, бо вони зрозумілі і для аналітиків, "
                "і для бізнес-стейкхолдерів та можуть стати легкими сигналами для списку спостереження.",
                "Domain-level cuts are useful because they are understandable to analysts and business stakeholders and can become lightweight watchlist signals.",
            ),
        }

    threshold_amount = raw_block["threshold_amount"]
    threshold_display = str(threshold_amount) if threshold_amount is not None else tr("н/д", "n/a")
    result_rows = [
        [
            row[0],
            row[1],
            row[2],
            row[3] if row[3] is not None else tr("н/д", "n/a"),
            row[4] if row[4] is not None else tr("н/д", "n/a"),
            row[5] if row[5] is not None else tr("н/д", "n/a"),
            row[6] if row[6] is not None else tr("н/д", "n/a"),
            row[7],
        ]
        for row in raw_block["result_rows"]
    ]
    return {
        "title": tr("Підтвердження по сумі транзакції", "Transaction amount evidence"),
        "intro": tr(
            f"Поточний запит використовує card1={raw_block['card1']} і "
            f"TransactionAmt={raw_block['transaction_amount']}. "
            "Цей блок порівнює суму з історичним базовим рівнем для того самого проксі клієнта.",
            f"The current request uses card1={raw_block['card1']} and "
            f"TransactionAmt={raw_block['transaction_amount']}. "
            "This block compares the amount with the historical baseline for the same customer proxy.",
        ),
        "summary_items": [
            {"label": "card1", "value": str(raw_block["card1"])},
            {"label": tr("Поточна сума", "Current amount"), "value": str(raw_block["transaction_amount"])},
            {"label": tr("Поріг", "Threshold"), "value": threshold_display},
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
            displayed_rows=int(raw_block["displayed_rows"]),
            lang=lang,
        ),
        "business_note": tr(
            "Сплески суми відносно базового рівня клієнта простіше обгрунтувати "
            "операційно, ніж сирі абсолютні правила по сумі, тому це хороший сигнал для ручної перевірки.",
            "Amount spikes relative to the customer baseline are easier to justify operationally than raw absolute amount rules, which makes this a strong manual-review signal.",
        ),
    }


def _localize_evidence_blocks(
    raw_blocks: list[dict[str, object]],
    lang: Language,
) -> list[dict[str, object]]:
    return [_localize_evidence_block(raw_block, lang) for raw_block in raw_blocks]


def load_score_evidence(
    data_dir: str,
    score_request: ScoreRequest,
    feature_values: dict[str, float],
    lang: Language,
) -> list[dict[str, object]]:
    # region debug-point language-switch-load-score-evidence
    started_at = perf_counter()
    # endregion debug-point language-switch-load-score-evidence
    base_data_path = Path(data_dir)
    dataset_dir = resolve_dataset_dir(base_data_path)
    if dataset_dir is None:
        # region debug-point language-switch-load-score-evidence
        append_debug_language_switch_log(
            "server_load_score_evidence",
            {
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                "localized_cache_hit": False,
                "raw_cache_hit": False,
                "dataset_dir_found": False,
                "lang": lang,
                "transaction_id": score_request.transaction_id,
            },
        )
        # endregion debug-point language-switch-load-score-evidence
        return []

    localized_cache_key = _build_score_evidence_cache_key(
        score_request,
        feature_values,
        lang,
    )
    cached_payload = load_cached_payload(base_data_path, localized_cache_key)
    if isinstance(cached_payload, list):
        # region debug-point language-switch-load-score-evidence
        append_debug_language_switch_log(
            "server_load_score_evidence",
            {
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                "localized_cache_hit": True,
                "raw_cache_hit": False,
                "dataset_dir_found": True,
                "block_count": len(cached_payload),
                "lang": lang,
                "transaction_id": score_request.transaction_id,
            },
        )
        # endregion debug-point language-switch-load-score-evidence
        return cached_payload

    raw_cache_key = _build_score_evidence_raw_cache_key(score_request, feature_values)
    raw_cached_payload = load_cached_payload(base_data_path, raw_cache_key)
    if isinstance(raw_cached_payload, list):
        evidence_blocks = _localize_evidence_blocks(raw_cached_payload, lang)
        store_cached_payload(base_data_path, localized_cache_key, evidence_blocks)
        # region debug-point language-switch-load-score-evidence
        append_debug_language_switch_log(
            "server_load_score_evidence",
            {
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                "localized_cache_hit": False,
                "raw_cache_hit": True,
                "dataset_dir_found": True,
                "block_count": len(evidence_blocks),
                "lang": lang,
                "transaction_id": score_request.transaction_id,
            },
        )
        # endregion debug-point language-switch-load-score-evidence
        return evidence_blocks

    connection = build_duckdb_connection(dataset_dir)
    raw_evidence_blocks: list[dict[str, object]] = []

    try:
        if feature_values.get("feat_productcd_c_flag", 0.0) >= 1.0:
            raw_evidence_blocks.append(
                _build_product_evidence_raw(connection, score_request)
            )

        if (
            feature_values.get("feat_high_risk_r_email_flag", 0.0) >= 1.0
            or feature_values.get("feat_missing_r_email_flag", 0.0) >= 1.0
        ):
            raw_evidence_blocks.append(
                _build_email_evidence_raw(
                    connection,
                    field_name="R_emaildomain",
                    field_value=score_request.r_emaildomain,
                )
            )

        if feature_values.get("feat_high_risk_p_email_flag", 0.0) >= 1.0:
            raw_evidence_blocks.append(
                _build_email_evidence_raw(
                    connection,
                    field_name="P_emaildomain",
                    field_value=score_request.p_emaildomain,
                )
            )

        if feature_values.get("feat_amount_gt_card1_avg_plus_3std", 0.0) >= 1.0:
            raw_evidence_blocks.append(
                _build_amount_evidence_raw(connection, score_request)
            )
    finally:
        connection.close()

    evidence_blocks = _localize_evidence_blocks(raw_evidence_blocks, lang)
    store_cached_payload(base_data_path, raw_cache_key, raw_evidence_blocks)
    store_cached_payload(base_data_path, localized_cache_key, evidence_blocks)
    # region debug-point language-switch-load-score-evidence
    append_debug_language_switch_log(
        "server_load_score_evidence",
        {
            "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            "localized_cache_hit": False,
            "raw_cache_hit": False,
            "dataset_dir_found": True,
            "block_count": len(evidence_blocks),
            "lang": lang,
            "transaction_id": score_request.transaction_id,
        },
    )
    # endregion debug-point language-switch-load-score-evidence
    return evidence_blocks
