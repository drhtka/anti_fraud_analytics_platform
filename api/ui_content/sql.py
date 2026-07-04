from __future__ import annotations

from pathlib import Path

from api.i18n import Language, translate
from api.ui_content.shared import (
    build_duckdb_connection,
    load_cached_payload,
    render_html_table,
    resolve_dataset_dir,
    store_cached_payload,
)


def load_sql_sections(data_dir: str, lang: Language) -> list[dict[str, object]]:
    tr = lambda uk, en: translate(lang, uk, en)
    base_data_path = Path(data_dir)
    dataset_dir = resolve_dataset_dir(base_data_path)
    if dataset_dir is None:
        return [
            {
                "title": tr("SQL-результати недоступні", "SQL results are unavailable"),
                "table_name": tr("Локальні дані відсутні", "Local data is missing"),
                "source_file": "sql/",
                "description": tr(
                    "SQL-екрану потрібні локальні IEEE-CIS CSV-файли в `data/raw/`, щоб показати таблиці результатів.",
                    "The SQL screen needs local IEEE-CIS CSV files in `data/raw/` to show result tables.",
                ),
                "query": tr(
                    "Поклади `train_transaction.csv` і `train_identity.csv` у `data/raw/`, щоб увімкнути живі SQL-блоки.",
                    "Put `train_transaction.csv` and `train_identity.csv` into `data/raw/` to enable live SQL blocks.",
                ),
                "reading_notes": [
                    tr(
                        "UI вже готовий до живих SQL-блоків на базі DuckDB.",
                        "The UI is already ready for live DuckDB-based SQL blocks.",
                    ),
                    tr(
                        "Як запасний варіант ті самі файли також можна покласти безпосередньо в data/.",
                        "As a fallback, the same files can also be placed directly in data/.",
                    ),
                    tr(
                        "Коли локальні CSV-файли будуть доступні, цей самий екран покаже реальні таблиці результатів.",
                        "Once the local CSV files are available, this same screen will show real result tables.",
                    ),
                ],
                "result_html": None,
            }
        ]

    cached_payload = load_cached_payload(base_data_path, f"sql_sections_{lang}")
    if isinstance(cached_payload, list):
        return cached_payload

    sql_sections = [
        {
            "title": tr("1. Загальна доля фроду", "1. Overall fraud share"),
            "table_name": tr("Загальна частка фроду", "Overall fraud share"),
            "source_file": "sql/ieee_cis_week_1_duckdb.sql",
            "description": tr(
                "Це перша базова перевірка: скільки всього транзакцій і наскільки рідкісним є фрод-клас.",
                "This is the first baseline check: how many transactions there are and how rare the fraud class is.",
            ),
            "business_takeaway": tr(
                "Фрод рідкісний, тому команді потрібна логіка ручної перевірки на основі порогів, а не наївні правила пропуску або блокування за сирим обсягом.",
                "Fraud is rare, so the team needs threshold-based manual review logic instead of naive allow/block rules based on raw volume.",
            ),
            "query": f"""
                SELECT COUNT(*) AS "{tr('Усього транзакцій', 'Total transactions')}",
                  SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) AS "{tr('Фродові транзакції', 'Fraud transactions')}",
                  ROUND(
                    100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                    4
                  ) AS "{tr('Частка фроду, %', 'Fraud share, %')}"
                FROM train_transaction
            """,
            "reading_notes": [
                tr(
                    "Використовуй цю таблицю, щоб пояснити дисбаланс класів до будь-якого моделювання.",
                    "Use this table to explain class imbalance before any modeling.",
                ),
                tr(
                    "Вона дає контекст, чому для антифроду важливі precision, recall і налаштування порога.",
                    "It gives context for why precision, recall, and threshold tuning matter in anti-fraud work.",
                ),
            ],
        },
        {
            "title": tr("2. Частка фроду за ProductCD", "2. Fraud share by ProductCD"),
            "table_name": tr("Ризик за ProductCD", "Risk by ProductCD"),
            "source_file": "sql/ieee_cis_week_1_duckdb.sql",
            "description": tr(
                "Ця сегментна таблиця показує, які продуктові групи виглядають ризикованішими за інші.",
                "This segment table shows which product groups look riskier than others.",
            ),
            "business_takeaway": tr(
                "Деякі продуктові сегменти потребують пильнішого моніторингу, бо концентрують більше фроду, ніж середній рівень по портфелю.",
                "Some product segments need closer monitoring because they concentrate more fraud than the portfolio baseline.",
            ),
            "query": f"""
                SELECT ProductCD AS "{tr('Продуктовий сегмент', 'Product segment')}",
                  COUNT(*) AS "{tr('Кількість транзакцій', 'Transaction count')}",
                  SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) AS "{tr('Фродові транзакції', 'Fraud transactions')}",
                  ROUND(
                    100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                    2
                  ) AS "{tr('Частка фроду, %', 'Fraud share, %')}"
                FROM train_transaction
                GROUP BY ProductCD
                ORDER BY "{tr('Частка фроду, %', 'Fraud share, %')}" DESC, "{tr('Кількість транзакцій', 'Transaction count')}" DESC
            """,
            "reading_notes": [
                tr(
                    "Це один із перших бізнес-зрозумілих сегментних зрізів у проєкті.",
                    "This is one of the first business-readable segment cuts in the project.",
                ),
                tr(
                    "Пізніше цей патерн підживлює і фрод-гіпотези, і легкі сигнали скорингу.",
                    "Later, this pattern feeds both fraud hypotheses and lightweight scoring signals.",
                ),
            ],
        },
        {
            "title": tr("3. Частка фроду за доменом отримувача", "3. Fraud share by recipient domain"),
            "table_name": tr("Ризик за доменом отримувача", "Risk by recipient domain"),
            "source_file": "sql/ieee_cis_week_1_duckdb.sql",
            "description": tr(
                "Домени електронної пошти отримувача можуть виявляти підозрілі маршрутизаційні патерни та слабкі сигнали довіри.",
                "Recipient email domains can reveal suspicious routing patterns and weak trust signals.",
            ),
            "business_takeaway": tr(
                "Домени отримувача з високим ризиком можна перетворити на список спостереження для аналітика або легкі сигнали скорингу без повного перенавчання моделі.",
                "High-risk recipient domains can be turned into an analyst watchlist or lightweight scoring signals without full model retraining.",
            ),
            "query": f"""
                SELECT COALESCE(R_emaildomain, '{tr('відсутній', 'missing')}') AS "{tr('Домен електронної пошти отримувача', 'Recipient email domain')}",
                  COUNT(*) AS "{tr('Кількість транзакцій', 'Transaction count')}",
                  SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) AS "{tr('Фродові транзакції', 'Fraud transactions')}",
                  ROUND(
                    100.0 * SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) / COUNT(*),
                    2
                  ) AS "{tr('Частка фроду, %', 'Fraud share, %')}"
                FROM train_transaction
                GROUP BY COALESCE(R_emaildomain, '{tr('відсутній', 'missing')}')
                HAVING COUNT(*) >= 100
                ORDER BY "{tr('Частка фроду, %', 'Fraud share, %')}" DESC, "{tr('Кількість транзакцій', 'Transaction count')}" DESC
                LIMIT 15
            """,
            "reading_notes": [
                tr(
                    "Цей блок добре пояснює, чому деякі домени стали кандидатами високого ризику.",
                    "This block clearly explains why some domains became high-risk candidates.",
                ),
                tr(
                    "Він напряму пов'язує SQL-дослідження з подальшими сигналами моделі та правилами.",
                    "It directly connects SQL exploration to later model signals and rules.",
                ),
            ],
        },
        {
            "title": tr(
                "4. Великі транзакції проти базового рівня клієнта",
                "4. Large transactions vs customer baseline",
            ),
            "table_name": tr("Аномалії суми відносно базового рівня", "Amount anomalies vs baseline"),
            "source_file": "sql/02_suspicious_patterns.sql",
            "description": tr(
                "Цей запит шукає транзакції, які є незвично великими порівняно з історією проксі клієнта.",
                "This query looks for transactions that are unusually large compared with the customer-proxy history.",
            ),
            "business_takeaway": tr(
                "Сплески суми відносно базового рівня клієнта є сильними кандидатами на ручну перевірку, бо їх простіше обгрунтувати операційно, ніж абсолютні правила по сумі.",
                "Amount spikes relative to the customer baseline are strong manual-review candidates because they are easier to justify operationally than absolute amount rules.",
            ),
            "query": f"""
                WITH customer_stats AS (
                  SELECT card1 AS customer_proxy,
                    AVG(TransactionAmt) AS avg_amount,
                    STDDEV_SAMP(TransactionAmt) AS std_amount
                  FROM train_transaction
                  GROUP BY card1
                )
                SELECT t.TransactionID AS "{tr('ID транзакції', 'Transaction ID')}",
                  t.card1 AS "{tr('Проксі клієнта', 'Customer proxy')}",
                  t.TransactionAmt AS "{tr('Сума транзакції', 'Transaction amount')}",
                  s.avg_amount AS "{tr('Середня сума клієнта', 'Average customer amount')}",
                  s.std_amount AS "{tr('Стандартне відхилення суми', 'Amount standard deviation')}"
                FROM train_transaction t
                  JOIN customer_stats s ON t.card1 = s.customer_proxy
                WHERE t.TransactionAmt > s.avg_amount + 3 * COALESCE(s.std_amount, 0)
                ORDER BY "{tr('Сума транзакції', 'Transaction amount')}" DESC
                LIMIT 15
            """,
            "reading_notes": [
                tr(
                    "Це класична антифрод-ідея: порівняти поточну суму з персональним базовим рівнем.",
                    "This is a classic anti-fraud idea: compare the current amount with a personal baseline.",
                ),
                tr(
                    "Пізніше ця сама логіка з'являється як `feat_amount_gt_card1_avg_plus_3std` у MVP-сценарії скорингу.",
                    "Later, the same logic appears as `feat_amount_gt_card1_avg_plus_3std` in the MVP scoring scenario.",
                ),
            ],
        },
    ]

    connection = build_duckdb_connection(dataset_dir)
    try:
        for section in sql_sections:
            result = connection.execute(section["query"])
            columns = [column[0] for column in result.description]
            rows = result.fetchall()
            section["result_html"] = render_html_table(columns, rows, displayed_rows=12, lang=lang)
    finally:
        connection.close()

    store_cached_payload(base_data_path, f"sql_sections_{lang}", sql_sections)
    return sql_sections
