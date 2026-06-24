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
        _, summary_rows = run_query(
            connection,
            """
            SELECT COUNT(*) AS "Усього транзакцій",
              ROUND(
                100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                4
              ) AS "Частка фроду, %",
              ROUND(AVG(TransactionAmt), 2) AS "Середня сума транзакції",
              COUNT(DISTINCT card1) AS "Проксі клієнтів"
            FROM train_transaction
            """,
        )
        _, identity_rows = run_query(
            connection,
            """
            SELECT ROUND(
                100.0 * COUNT(i.TransactionID) / COUNT(t.TransactionID),
                2
              ) AS "Покриття identity, %"
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
            "description": "Повна таблиця транзакцій, яка використовується в поточному демонстраційному сценарії.",
        },
        {
            "label": "Доля фроду",
            "value": f"{summary_row[1]}%",
            "description": "Дисбаланс цільового класу, який впливає на поріг рішення та обсяг ручної перевірки.",
        },
        {
            "label": "Середня сума транзакції",
            "value": f"{summary_row[2]}",
            "description": "Швидкий базовий орієнтир, щоб оцінити, чи виглядає поточна сума нетипово.",
        },
        {
            "label": "Проксі клієнтів",
            "value": f"{int(summary_row[3]):,}",
            "description": "Унікальні значення `card1`, які використовуються як спрощене проксі клієнта.",
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
                    "Як запасний варіант застосунок також підтримує ті самі файли безпосередньо в data/.",
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
            SELECT COUNT(*) AS "Усього транзакцій",
              COUNT(DISTINCT card1) AS "Проксі клієнтів",
              ROUND(AVG(TransactionAmt), 2) AS "Середня сума транзакції",
              ROUND(MAX(TransactionAmt), 2) AS "Максимальна сума транзакції"
            FROM train_transaction
            """,
        )

        imbalance_columns, imbalance_rows = run_query(
            connection,
            """
            SELECT COUNT(*) AS "Усього транзакцій",
              SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) AS "Фродові транзакції",
              SUM(CASE WHEN isFraud = 0 THEN 1 ELSE 0 END) AS "Нефродові транзакції",
              ROUND(
                100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                4
              ) AS "Частка фроду, %"
            FROM train_transaction
            """,
        )

        email_domain_columns, email_domain_rows = run_query(
            connection,
            """
            SELECT COALESCE(R_emaildomain, 'відсутній') AS "Домен електронної пошти отримувача",
              COUNT(*) AS "Кількість транзакцій",
              ROUND(
                100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                2
              ) AS "Частка фроду, %"
            FROM train_transaction
            GROUP BY COALESCE(R_emaildomain, 'відсутній')
            HAVING COUNT(*) >= 100
            ORDER BY "Частка фроду, %" DESC, "Кількість транзакцій" DESC
            LIMIT 12
            """,
        )

        product_columns, product_rows = run_query(
            connection,
            """
            SELECT ProductCD AS "Продуктовий сегмент",
              COUNT(*) AS "Кількість транзакцій",
              ROUND(
                100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                2
              ) AS "Частка фроду, %"
            FROM train_transaction
            GROUP BY ProductCD
            ORDER BY "Частка фроду, %" DESC, "Кількість транзакцій" DESC
            """,
        )

        payload = [
            {
                "title": "1. Швидкий огляд даних",
                "table_name": "Огляд датасету",
                "description": "Перший орієнтаційний блок із розміром датасету, масштабом сум і покриттям проксі клієнтів.",
                "notes": build_notes(
                    "Починаємо з розміру таблиці, базових метрик по сумах і кількості проксі клієнтів.",
                    f"У `train_transaction` {transaction_columns} колонок, а у `train_identity` {identity_columns} колонок.",
                    "Це перший крок орієнтації перед фокусом на фрод-патернах.",
                ),
                "outputs": [
                    {"kind": "html", "content": render_html_table(overview_columns, overview_rows, displayed_rows=10)},
                ],
            },
            {
                "title": "2. Цільовий клас і дисбаланс",
                "table_name": "Дисбаланс цільового класу",
                "description": "Компактний зріз рідкісності фроду, який пояснює, чому в антифроді не можна покладатися лише на точність.",
                "notes": build_notes(
                    "Для антифроду це обов'язкова рання перевірка, бо фрод зазвичай є рідкісним.",
                    "Цей блок пояснює, чому далі в проєкті важливі налаштування порога й навантаження на ручну перевірку.",
                ),
                "outputs": [
                    {"kind": "html", "content": render_html_table(imbalance_columns, imbalance_rows, displayed_rows=10)},
                    {
                        "kind": "image",
                        "content": render_chart(
                            ["нефрод", "фрод"],
                            [float(imbalance_rows[0][2]), float(imbalance_rows[0][1])],
                            "Дисбаланс класів у `train_transaction`",
                            color="#dc2626",
                        ),
                    },
                ],
            },
            {
                "title": "3. Патерни продуктових сегментів",
                "table_name": "Ризик за продуктовими сегментами",
                "description": "Таблиця на рівні сегментів, яка показує, які групи ознаки `ProductCD` виглядають ризикованішими ще до навчання моделі.",
                "notes": build_notes(
                    "Цей блок показує, які продуктові сегменти виділяються ще до навчання моделі.",
                    "Ознака `ProductCD` далі стає частиною і антифрод-гіпотез, і MVP-ознак.",
                ),
                "outputs": [
                    {"kind": "html", "content": render_html_table(product_columns, product_rows, displayed_rows=10)},
                    {
                        "kind": "image",
                        "content": render_chart(
                            [str(row[0]) for row in product_rows],
                            [float(row[2]) for row in product_rows],
                            "Частка фроду за `ProductCD`",
                        ),
                    },
                ],
            },
            {
                "title": "4. Патерни доменів електронної пошти отримувача",
                "table_name": "Ризик за доменами отримувача",
                "description": "Зріз на рівні доменів, який допомагає пояснити, чому деякі домени отримувача стали сильними підозрілими сигналами.",
                "notes": build_notes(
                    "Аналіз доменів електронної пошти корисний, бо він зрозумілий і аналітикам, і бізнес-стейкхолдерам.",
                    "Цей блок також напряму пов'язаний із подальшими ідеями правил та MVP-сигналами скорингу.",
                ),
                "outputs": [
                    {"kind": "html", "content": render_html_table(email_domain_columns, email_domain_rows, displayed_rows=12)},
                    {
                        "kind": "image",
                        "content": render_chart(
                            [str(row[0]) for row in email_domain_rows[:8]],
                            [float(row[2]) for row in email_domain_rows[:8]],
                            "Частка фроду за доменом електронної пошти отримувача",
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
