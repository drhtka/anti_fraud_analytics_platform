from __future__ import annotations

from pathlib import Path

from api.i18n import Language, translate
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


def load_eda_summary(data_dir: str, lang: Language) -> list[dict[str, str]]:
    tr = lambda uk, en: translate(lang, uk, en)
    base_data_path = Path(data_dir)
    dataset_dir = resolve_dataset_dir(base_data_path)
    if dataset_dir is None:
        return []

    cached_payload = load_cached_payload(base_data_path, f"eda_summary_{lang}")
    if isinstance(cached_payload, list):
        return cached_payload

    connection = build_duckdb_connection(dataset_dir)
    try:
        _, summary_rows = run_query(
            connection,
            f"""
            SELECT COUNT(*) AS "{tr('Усього транзакцій', 'Total transactions')}",
              ROUND(
                100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                4
              ) AS "{tr('Частка фроду, %', 'Fraud share, %')}",
              ROUND(AVG(TransactionAmt), 2) AS "{tr('Середня сума транзакції', 'Average transaction amount')}",
              COUNT(DISTINCT card1) AS "{tr('Проксі клієнтів', 'Customer proxies')}"
            FROM train_transaction
            """,
        )
        _, identity_rows = run_query(
            connection,
            f"""
            SELECT ROUND(
                100.0 * COUNT(i.TransactionID) / COUNT(t.TransactionID),
                2
              ) AS "{tr('Покриття identity, %', 'Identity coverage, %')}"
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
            "label": translate(lang, "Усього транзакцій", "Total transactions"),
            "value": f"{int(summary_row[0]):,}",
            "description": translate(
                lang,
                "Повна таблиця транзакцій, яка використовується в поточному демонстраційному сценарії.",
                "The full transaction table used in the current demo scenario.",
            ),
        },
        {
            "label": translate(lang, "Доля фроду", "Fraud share"),
            "value": f"{summary_row[1]}%",
            "description": translate(
                lang,
                "Дисбаланс цільового класу, який впливає на поріг рішення та обсяг ручної перевірки.",
                "Target-class imbalance that affects the decision threshold and manual review volume.",
            ),
        },
        {
            "label": translate(lang, "Середня сума транзакції", "Average transaction amount"),
            "value": f"{summary_row[2]}",
            "description": translate(
                lang,
                "Швидкий базовий орієнтир, щоб оцінити, чи виглядає поточна сума нетипово.",
                "A quick baseline to judge whether the current amount looks unusual.",
            ),
        },
        {
            "label": translate(lang, "Проксі клієнтів", "Customer proxies"),
            "value": f"{int(summary_row[3]):,}",
            "description": translate(
                lang,
                "Унікальні значення `card1`, які використовуються як спрощене проксі клієнта.",
                "Unique `card1` values used as a simplified customer proxy.",
            ),
        },
        {
            "label": translate(lang, "Рівень збігу identity", "Identity match rate"),
            "value": f"{identity_row[0]}%",
            "description": translate(
                lang,
                "Частка транзакцій, які мають пов'язаний рядок у `train_identity`.",
                "Share of transactions that have a linked row in `train_identity`.",
            ),
        },
    ]
    store_cached_payload(base_data_path, f"eda_summary_{lang}", payload)
    return payload


def load_eda_sections(data_dir: str, lang: Language) -> list[dict[str, object]]:
    tr = lambda uk, en: translate(lang, uk, en)
    base_data_path = Path(data_dir)
    dataset_dir = resolve_dataset_dir(base_data_path)
    if dataset_dir is None:
        return [
            {
                "title": tr("EDA-дані недоступні", "EDA data is unavailable"),
                "notes": build_notes(
                    tr(
                        "Поклади train_transaction.csv і train_identity.csv у data/raw/, щоб побудувати EDA-екран.",
                        "Put train_transaction.csv and train_identity.csv into data/raw/ to build the EDA screen.",
                    ),
                    tr(
                        "Як запасний варіант застосунок також підтримує ті самі файли безпосередньо в data/.",
                        "As a fallback, the app also supports the same files directly in data/.",
                    ),
                    tr(
                        "EDA-інтерфейс читає локальні CSV-файли напряму, а не виводи ноутбуків.",
                        "The EDA interface reads local CSV files directly rather than notebook outputs.",
                    ),
                ),
                "outputs": [],
            }
        ]

    cached_payload = load_cached_payload(base_data_path, f"eda_sections_{lang}")
    if isinstance(cached_payload, list):
        return cached_payload

    connection = build_duckdb_connection(dataset_dir)
    try:
        transaction_columns = len(connection.execute("DESCRIBE train_transaction").fetchall())
        identity_columns = len(connection.execute("DESCRIBE train_identity").fetchall())

        overview_columns, overview_rows = run_query(
            connection,
            f"""
            SELECT COUNT(*) AS "{tr('Усього транзакцій', 'Total transactions')}",
              COUNT(DISTINCT card1) AS "{tr('Проксі клієнтів', 'Customer proxies')}",
              ROUND(AVG(TransactionAmt), 2) AS "{tr('Середня сума транзакції', 'Average transaction amount')}",
              ROUND(MAX(TransactionAmt), 2) AS "{tr('Максимальна сума транзакції', 'Maximum transaction amount')}"
            FROM train_transaction
            """,
        )

        imbalance_columns, imbalance_rows = run_query(
            connection,
            f"""
            SELECT COUNT(*) AS "{tr('Усього транзакцій', 'Total transactions')}",
              SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) AS "{tr('Фродові транзакції', 'Fraud transactions')}",
              SUM(CASE WHEN isFraud = 0 THEN 1 ELSE 0 END) AS "{tr('Нефродові транзакції', 'Non-fraud transactions')}",
              ROUND(
                100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                4
              ) AS "{tr('Частка фроду, %', 'Fraud share, %')}"
            FROM train_transaction
            """,
        )

        email_domain_columns, email_domain_rows = run_query(
            connection,
            f"""
            SELECT COALESCE(R_emaildomain, '{tr('відсутній', 'missing')}') AS "{tr('Домен електронної пошти отримувача', 'Recipient email domain')}",
              COUNT(*) AS "{tr('Кількість транзакцій', 'Transaction count')}",
              ROUND(
                100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                2
              ) AS "{tr('Частка фроду, %', 'Fraud share, %')}"
            FROM train_transaction
            GROUP BY COALESCE(R_emaildomain, '{tr('відсутній', 'missing')}')
            HAVING COUNT(*) >= 100
            ORDER BY "{tr('Частка фроду, %', 'Fraud share, %')}" DESC, "{tr('Кількість транзакцій', 'Transaction count')}" DESC
            LIMIT 12
            """,
        )

        product_columns, product_rows = run_query(
            connection,
            f"""
            SELECT ProductCD AS "{tr('Продуктовий сегмент', 'Product segment')}",
              COUNT(*) AS "{tr('Кількість транзакцій', 'Transaction count')}",
              ROUND(
                100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                2
              ) AS "{tr('Частка фроду, %', 'Fraud share, %')}"
            FROM train_transaction
            GROUP BY ProductCD
            ORDER BY "{tr('Частка фроду, %', 'Fraud share, %')}" DESC, "{tr('Кількість транзакцій', 'Transaction count')}" DESC
            """,
        )

        payload = [
            {
                "title": tr("1. Швидкий огляд даних", "1. Quick data overview"),
                "table_name": tr("Огляд датасету", "Dataset overview"),
                "description": tr(
                    "Перший орієнтаційний блок із розміром датасету, масштабом сум і покриттям проксі клієнтів.",
                    "A first orientation block with dataset size, amount scale, and customer-proxy coverage.",
                ),
                "notes": build_notes(
                    tr(
                        "Починаємо з розміру таблиці, базових метрик по сумах і кількості проксі клієнтів.",
                        "We start with table size, basic amount metrics, and the number of customer proxies.",
                    ),
                    tr(
                        f"У `train_transaction` {transaction_columns} колонок, а у `train_identity` {identity_columns} колонок.",
                        f"`train_transaction` has {transaction_columns} columns, and `train_identity` has {identity_columns} columns.",
                    ),
                    tr(
                        "Це перший крок орієнтації перед фокусом на фрод-патернах.",
                        "This is the first orientation step before focusing on fraud patterns.",
                    ),
                ),
                "outputs": [
                    {
                        "kind": "html",
                        "content": render_html_table(
                            overview_columns,
                            overview_rows,
                            displayed_rows=10,
                            lang=lang,
                        ),
                    },
                ],
            },
            {
                "title": tr("2. Цільовий клас і дисбаланс", "2. Target class and imbalance"),
                "table_name": tr("Дисбаланс цільового класу", "Target-class imbalance"),
                "description": tr(
                    "Компактний зріз рідкісності фроду, який пояснює, чому в антифроді не можна покладатися лише на точність.",
                    "A compact view of fraud rarity that explains why anti-fraud work cannot rely on accuracy alone.",
                ),
                "notes": build_notes(
                    tr(
                        "Для антифроду це обов'язкова рання перевірка, бо фрод зазвичай є рідкісним.",
                        "For anti-fraud, this is a mandatory early check because fraud is usually rare.",
                    ),
                    tr(
                        "Цей блок пояснює, чому далі в проєкті важливі налаштування порога й навантаження на ручну перевірку.",
                        "This block explains why threshold tuning and manual review load matter later in the project.",
                    ),
                ),
                "outputs": [
                    {
                        "kind": "html",
                        "content": render_html_table(
                            imbalance_columns,
                            imbalance_rows,
                            displayed_rows=10,
                            lang=lang,
                        ),
                    },
                    {
                        "kind": "image",
                        "content": render_chart(
                            [tr("нефрод", "non-fraud"), tr("фрод", "fraud")],
                            [float(imbalance_rows[0][2]), float(imbalance_rows[0][1])],
                            tr("Дисбаланс класів у `train_transaction`", "Class imbalance in `train_transaction`"),
                            lang=lang,
                            color="#dc2626",
                        ),
                    },
                ],
            },
            {
                "title": tr("3. Патерни продуктових сегментів", "3. Product-segment patterns"),
                "table_name": tr("Ризик за продуктовими сегментами", "Risk by product segment"),
                "description": tr(
                    "Таблиця на рівні сегментів, яка показує, які групи ознаки `ProductCD` виглядають ризикованішими ще до навчання моделі.",
                    "A segment-level table that shows which `ProductCD` groups look riskier even before model training.",
                ),
                "notes": build_notes(
                    tr(
                        "Цей блок показує, які продуктові сегменти виділяються ще до навчання моделі.",
                        "This block shows which product segments stand out even before model training.",
                    ),
                    tr(
                        "Ознака `ProductCD` далі стає частиною і антифрод-гіпотез, і MVP-ознак.",
                        "`ProductCD` later becomes part of both anti-fraud hypotheses and MVP features.",
                    ),
                ),
                "outputs": [
                    {
                        "kind": "html",
                        "content": render_html_table(
                            product_columns,
                            product_rows,
                            displayed_rows=10,
                            lang=lang,
                        ),
                    },
                    {
                        "kind": "image",
                        "content": render_chart(
                            [str(row[0]) for row in product_rows],
                            [float(row[2]) for row in product_rows],
                            tr("Частка фроду за `ProductCD`", "Fraud share by `ProductCD`"),
                            lang=lang,
                        ),
                    },
                ],
            },
            {
                "title": tr(
                    "4. Патерни доменів електронної пошти отримувача",
                    "4. Recipient email-domain patterns",
                ),
                "table_name": tr("Ризик за доменами отримувача", "Risk by recipient domain"),
                "description": tr(
                    "Зріз на рівні доменів, який допомагає пояснити, чому деякі домени отримувача стали сильними підозрілими сигналами.",
                    "A domain-level view that helps explain why some recipient domains became strong suspicious signals.",
                ),
                "notes": build_notes(
                    tr(
                        "Аналіз доменів електронної пошти корисний, бо він зрозумілий і аналітикам, і бізнес-стейкхолдерам.",
                        "Email-domain analysis is useful because it is understandable to both analysts and business stakeholders.",
                    ),
                    tr(
                        "Цей блок також напряму пов'язаний із подальшими ідеями правил та MVP-сигналами скорингу.",
                        "This block is also directly connected to later rule ideas and MVP scoring signals.",
                    ),
                ),
                "outputs": [
                    {
                        "kind": "html",
                        "content": render_html_table(
                            email_domain_columns,
                            email_domain_rows,
                            displayed_rows=12,
                            lang=lang,
                        ),
                    },
                    {
                        "kind": "image",
                        "content": render_chart(
                            [str(row[0]) for row in email_domain_rows[:8]],
                            [float(row[2]) for row in email_domain_rows[:8]],
                            tr(
                                "Частка фроду за доменом електронної пошти отримувача",
                                "Fraud share by recipient email domain",
                            ),
                            lang=lang,
                            color="#7c3aed",
                        ),
                    },
                ],
            },
        ]
    finally:
        connection.close()

    store_cached_payload(base_data_path, f"eda_sections_{lang}", payload)
    return payload
