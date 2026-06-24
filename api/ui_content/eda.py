from __future__ import annotations

from pathlib import Path

from api.ui_content.shared import (
    build_duckdb_connection,
    build_notes,
    load_cached_payload,
    render_chart,
    render_html_table,
    resolve_dataset_dir,
    run_query,
    store_cached_payload,
)


def load_eda_summary(data_dir: str) -> list[dict[str, str]]:
    base_data_path = Path(data_dir)
    dataset_dir = resolve_dataset_dir(base_data_path)
    if dataset_dir is None:
        return []

    cached_payload = load_cached_payload(base_data_path, "eda_summary")
    if isinstance(cached_payload, list):
        return cached_payload

    connection = build_duckdb_connection(dataset_dir)
    try:
        summary_columns, summary_rows = run_query(
            connection,
            """
            SELECT COUNT(*) AS total_transactions,
              ROUND(
                100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                4
              ) AS fraud_rate_pct,
              ROUND(AVG(TransactionAmt), 2) AS avg_transaction_amount,
              COUNT(DISTINCT card1) AS customer_proxy_count
            FROM train_transaction
            """,
        )
        identity_columns, identity_rows = run_query(
            connection,
            """
            SELECT ROUND(
                100.0 * COUNT(i.TransactionID) / COUNT(t.TransactionID),
                2
              ) AS identity_match_rate_pct
            FROM train_transaction t
              LEFT JOIN train_identity i USING (TransactionID)
            """,
        )
    finally:
        connection.close()

    summary_row = summary_rows[0]
    identity_row = identity_rows[0]
    payload = [
        {
            "label": "Усього транзакцій",
            "value": f"{int(summary_row[0]):,}",
            "description": "Повна таблиця транзакцій, яка використовується в поточному demo-flow.",
        },
        {
            "label": "Доля фроду",
            "value": f"{summary_row[1]}%",
            "description": "Дисбаланс target, який впливає на поріг рішення та обсяг ручної перевірки.",
        },
        {
            "label": "Середня сума транзакції",
            "value": f"{summary_row[2]}",
            "description": "Швидкий baseline, щоб оцінити, чи виглядає поточна сума нетипово.",
        },
        {
            "label": "Customer proxies",
            "value": f"{int(summary_row[3]):,}",
            "description": "Унікальні значення `card1`, які використовуються як lightweight customer proxy.",
        },
        {
            "label": "Рівень збігу identity",
            "value": f"{identity_row[0]}%",
            "description": "Частка транзакцій, які мають пов'язаний рядок у `train_identity`.",
        },
    ]
    store_cached_payload(base_data_path, "eda_summary", payload)
    return payload


def load_eda_sections(data_dir: str) -> list[dict[str, object]]:
    base_data_path = Path(data_dir)
    dataset_dir = resolve_dataset_dir(base_data_path)
    if dataset_dir is None:
        return [
            {
                "title": "EDA-дані недоступні",
                "notes": build_notes(
                    "Поклади train_transaction.csv і train_identity.csv у data/raw/, щоб побудувати EDA-екран.",
                    "Як fallback застосунок також підтримує ті самі файли безпосередньо в data/.",
                    "EDA-інтерфейс читає локальні CSV-файли напряму, а не виводи ноутбуків.",
                ),
                "outputs": [],
            }
        ]

    cached_payload = load_cached_payload(base_data_path, "eda_sections")
    if isinstance(cached_payload, list):
        return cached_payload

    connection = build_duckdb_connection(dataset_dir)
    try:
        transaction_columns = len(connection.execute("DESCRIBE train_transaction").fetchall())
        identity_columns = len(connection.execute("DESCRIBE train_identity").fetchall())

        overview_columns, overview_rows = run_query(
            connection,
            """
            SELECT COUNT(*) AS total_transactions,
              COUNT(DISTINCT card1) AS customer_proxy_count,
              ROUND(AVG(TransactionAmt), 2) AS avg_transaction_amount,
              ROUND(MAX(TransactionAmt), 2) AS max_transaction_amount
            FROM train_transaction
            """,
        )

        imbalance_columns, imbalance_rows = run_query(
            connection,
            """
            SELECT COUNT(*) AS total_transactions,
              SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) AS fraud_transactions,
              SUM(CASE WHEN isFraud = 0 THEN 1 ELSE 0 END) AS non_fraud_transactions,
              ROUND(
                100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                4
              ) AS fraud_rate_pct
            FROM train_transaction
            """,
        )

        email_domain_columns, email_domain_rows = run_query(
            connection,
            """
            SELECT COALESCE(R_emaildomain, 'missing') AS recipient_email_domain,
              COUNT(*) AS tx_count,
              ROUND(
                100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                2
              ) AS fraud_rate_pct
            FROM train_transaction
            GROUP BY recipient_email_domain
            HAVING COUNT(*) >= 100
            ORDER BY fraud_rate_pct DESC, tx_count DESC
            LIMIT 12
            """,
        )

        product_columns, product_rows = run_query(
            connection,
            """
            SELECT ProductCD,
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

        payload = [
            {
                "title": "1. Швидкий огляд даних",
                "table_name": "eda_dataset_overview",
                "description": "Перший орієнтаційний блок із розміром датасету, масштабом сум і покриттям customer proxy.",
                "notes": build_notes(
                    "Починаємо з розміру таблиці, базових метрик по сумах і кількості customer proxy.",
                    f"У train_transaction {transaction_columns} колонок, а у train_identity {identity_columns} колонок.",
                    "Це перший крок орієнтації перед fraud-специфічними зрізами.",
                ),
                "outputs": [
                    {"kind": "html", "content": render_html_table(overview_columns, overview_rows, displayed_rows=10)},
                ],
            },
            {
                "title": "2. Target і дисбаланс класів",
                "table_name": "eda_target_imbalance",
                "description": "Компактний зріз рідкісності фроду, який пояснює, чому в anti-fraud не можна покладатися лише на accuracy.",
                "notes": build_notes(
                    "Для anti-fraud це обов'язкова рання перевірка, бо фрод зазвичай є рідкісним.",
                    "Цей блок пояснює, чому далі в проєкті важливі tuning порога й review load.",
                ),
                "outputs": [
                    {"kind": "html", "content": render_html_table(imbalance_columns, imbalance_rows, displayed_rows=10)},
                    {
                        "kind": "image",
                        "content": render_chart(
                            ["non_fraud", "fraud"],
                            [float(imbalance_rows[0][2]), float(imbalance_rows[0][1])],
                            "Дисбаланс класів у train_transaction",
                            color="#dc2626",
                        ),
                    },
                ],
            },
            {
                "title": "3. Патерни продуктових сегментів",
                "table_name": "eda_product_segment_risk",
                "description": "Таблиця на рівні сегментів, яка показує, які групи ProductCD виглядають ризикованішими ще до навчання моделі.",
                "notes": build_notes(
                    "Цей блок показує, які продуктові сегменти виділяються ще до навчання моделі.",
                    "ProductCD далі стає частиною і anti-fraud гіпотез, і MVP-ознак.",
                ),
                "outputs": [
                    {"kind": "html", "content": render_html_table(product_columns, product_rows, displayed_rows=10)},
                    {
                        "kind": "image",
                        "content": render_chart(
                            [str(row[0]) for row in product_rows],
                            [float(row[2]) for row in product_rows],
                            "Fraud rate за ProductCD",
                        ),
                    },
                ],
            },
            {
                "title": "4. Патерни доменів email отримувача",
                "table_name": "eda_recipient_email_domain_risk",
                "description": "Зріз на рівні доменів, який допомагає пояснити, чому деякі домени отримувача стали сильними suspicious-сигналами.",
                "notes": build_notes(
                    "Аналіз email-доменів корисний, бо він зрозумілий і аналітикам, і бізнес-стейкхолдерам.",
                    "Цей блок також напряму пов'язаний із подальшими rule-ідеями та MVP scoring signals.",
                ),
                "outputs": [
                    {"kind": "html", "content": render_html_table(email_domain_columns, email_domain_rows, displayed_rows=12)},
                    {
                        "kind": "image",
                        "content": render_chart(
                            [str(row[0]) for row in email_domain_rows[:8]],
                            [float(row[2]) for row in email_domain_rows[:8]],
                            "Fraud rate за доменом email отримувача",
                            color="#7c3aed",
                        ),
                    },
                ],
            },
        ]
    finally:
        connection.close()

    store_cached_payload(base_data_path, "eda_sections", payload)
    return payload
