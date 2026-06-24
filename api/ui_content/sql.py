from __future__ import annotations

from pathlib import Path

from api.ui_content.shared import (
    build_duckdb_connection,
    load_cached_payload,
    render_html_table,
    resolve_dataset_dir,
    store_cached_payload,
)


def load_sql_sections(data_dir: str) -> list[dict[str, object]]:
    base_data_path = Path(data_dir)
    dataset_dir = resolve_dataset_dir(base_data_path)
    if dataset_dir is None:
        return [
            {
                "title": "SQL-результати недоступні",
                "table_name": "Локальні дані відсутні",
                "source_file": "sql/",
                "description": "SQL-екрану потрібні локальні IEEE-CIS CSV-файли в `data/raw/`, щоб показати таблиці результатів.",
                "query": "Поклади `train_transaction.csv` і `train_identity.csv` у `data/raw/`, щоб увімкнути живі SQL-блоки.",
                "reading_notes": [
                    "UI вже готовий до живих SQL-блоків на базі DuckDB.",
                    "Як запасний варіант ті самі файли також можна покласти безпосередньо в data/.",
                    "Коли локальні CSV-файли будуть доступні, цей самий екран покаже реальні таблиці результатів.",
                ],
                "result_html": None,
            }
        ]

    cached_payload = load_cached_payload(base_data_path, "sql_sections")
    if isinstance(cached_payload, list):
        return cached_payload

    sql_sections = [
        {
            "title": "1. Загальна доля фроду",
            "table_name": "Загальна частка фроду",
            "source_file": "sql/ieee_cis_week_1_duckdb.sql",
            "description": "Це перша базова перевірка: скільки всього транзакцій і наскільки рідкісним є фрод-клас.",
            "business_takeaway": "Фрод рідкісний, тому команді потрібна логіка ручної перевірки на основі порогів, а не наївні правила пропуску або блокування за сирим обсягом.",
            "query": """
                SELECT COUNT(*) AS "Усього транзакцій",
                  SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) AS "Фродові транзакції",
                  ROUND(
                    100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                    4
                  ) AS "Частка фроду, %"
                FROM train_transaction
            """,
            "reading_notes": [
                "Використовуй цю таблицю, щоб пояснити дисбаланс класів до будь-якого моделювання.",
                "Вона дає контекст, чому для антифроду важливі precision, recall і налаштування порога.",
            ],
        },
        {
            "title": "2. Частка фроду за ProductCD",
            "table_name": "Ризик за ProductCD",
            "source_file": "sql/ieee_cis_week_1_duckdb.sql",
            "description": "Ця сегментна таблиця показує, які продуктові групи виглядають ризикованішими за інші.",
            "business_takeaway": "Деякі продуктові сегменти потребують пильнішого моніторингу, бо концентрують більше фроду, ніж середній рівень по портфелю.",
            "query": """
                SELECT ProductCD AS "Продуктовий сегмент",
                  COUNT(*) AS "Кількість транзакцій",
                  SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) AS "Фродові транзакції",
                  ROUND(
                    100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                    2
                  ) AS "Частка фроду, %"
                FROM train_transaction
                GROUP BY ProductCD
                ORDER BY "Частка фроду, %" DESC, "Кількість транзакцій" DESC
            """,
            "reading_notes": [
                "Це один із перших бізнес-зрозумілих сегментних зрізів у проєкті.",
                "Пізніше цей патерн підживлює і фрод-гіпотези, і легкі сигнали скорингу.",
            ],
        },
        {
            "title": "3. Частка фроду за доменом отримувача",
            "table_name": "Ризик за доменом отримувача",
            "source_file": "sql/ieee_cis_week_1_duckdb.sql",
            "description": "Домени електронної пошти отримувача можуть виявляти підозрілі маршрутизаційні патерни та слабкі сигнали довіри.",
            "business_takeaway": "Домени отримувача з високим ризиком можна перетворити на список спостереження для аналітика або легкі сигнали скорингу без повного перенавчання моделі.",
            "query": """
                SELECT COALESCE(R_emaildomain, 'відсутній') AS "Домен електронної пошти отримувача",
                  COUNT(*) AS "Кількість транзакцій",
                  SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) AS "Фродові транзакції",
                  ROUND(
                    100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                    2
                  ) AS "Частка фроду, %"
                FROM train_transaction
                GROUP BY COALESCE(R_emaildomain, 'відсутній')
                HAVING COUNT(*) >= 100
                ORDER BY "Частка фроду, %" DESC, "Кількість транзакцій" DESC
                LIMIT 15
            """,
            "reading_notes": [
                "Цей блок добре пояснює, чому деякі домени стали кандидатами високого ризику.",
                "Він напряму пов'язує SQL-дослідження з подальшими сигналами моделі та правилами.",
            ],
        },
        {
            "title": "4. Великі транзакції проти базового рівня клієнта",
            "table_name": "Аномалії суми відносно базового рівня",
            "source_file": "sql/02_suspicious_patterns.sql",
            "description": "Цей запит шукає транзакції, які є незвично великими порівняно з історією проксі клієнта.",
            "business_takeaway": "Сплески суми відносно базового рівня клієнта є сильними кандидатами на ручну перевірку, бо їх простіше обгрунтувати операційно, ніж абсолютні правила по сумі.",
            "query": """
                WITH customer_stats AS (
                  SELECT card1 AS customer_proxy,
                    AVG(TransactionAmt) AS avg_amount,
                    STDDEV_SAMP(TransactionAmt) AS std_amount
                  FROM train_transaction
                  GROUP BY card1
                )
                SELECT t.TransactionID AS "ID транзакції",
                  t.card1 AS "Проксі клієнта",
                  t.TransactionAmt AS "Сума транзакції",
                  s.avg_amount AS "Середня сума клієнта",
                  s.std_amount AS "Стандартне відхилення суми"
                FROM train_transaction t
                  JOIN customer_stats s ON t.card1 = s.customer_proxy
                WHERE t.TransactionAmt > s.avg_amount + 3 * COALESCE(s.std_amount, 0)
                ORDER BY "Сума транзакції" DESC
                LIMIT 15
            """,
            "reading_notes": [
                "Це класична антифрод-ідея: порівняти поточну суму з персональним базовим рівнем.",
                "Пізніше ця сама логіка з'являється як `feat_amount_gt_card1_avg_plus_3std` у MVP-сценарії скорингу.",
            ],
        },
    ]

    connection = build_duckdb_connection(dataset_dir)
    try:
        for section in sql_sections:
            result = connection.execute(section["query"])
            columns = [column[0] for column in result.description]
            rows = result.fetchall()
            section["result_html"] = render_html_table(columns, rows, displayed_rows=12)
    finally:
        connection.close()

    store_cached_payload(base_data_path, "sql_sections", sql_sections)
    return sql_sections
