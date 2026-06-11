# Anti-Fraud Analytics Platform

Учебный портфельный проект под вакансию в аналитике, рисках и антифроде.

## Цель проекта

Показать на одном кейсе, что ты умеешь:

- работать с транзакционными данными;
- делать `SQL` и `EDA`;
- формировать антифрод-гипотезы;
- строить признаки и baseline `ML`-модель;
- объяснять результат в бизнес-контексте;
- упаковывать решение в `FastAPI`.

## Структура проекта

- `data/` - описание источника данных и локальные датасеты;
- `sql/` - аналитические запросы и витрины признаков;
- `notebooks/` - `EDA` и исследовательские ноутбуки;
- `src/` - подготовка данных, признаки, правила и модель;
- `api/` - `FastAPI` приложение и схемы запросов;
- `docs/` - рабочие материалы, разложенные по проектам и неделям.

## Рекомендуемый порядок работы

1. Выбрать датасет.
2. Описать поля и бизнес-смысл таблиц.
3. Выполнить базовый `EDA`.
4. Написать первые аналитические `SQL`-запросы.
5. Сформировать rule-based антифрод-правила.
6. Подготовить признаки для baseline модели.
7. Обучить модель и сравнить ее с правилами.
8. Завернуть скоринг и explain в `API`.

## Стартовые файлы

- `docs/new_chat_handoff.md` - короткий handoff для продолжения в новом чате;
- `docs/vacancy_learning_plan.md` - план обучения и привязка к вакансии;
- `docs/docs_map.md` - карта документации;
- `docs/ieee_cis_fraud_detection/project_map.md` - карта проекта `IEEE-CIS`;
- `docs/ieee_cis_fraud_detection/week_1/week_1_map.md` - карта материалов первой недели;
- `docs/ieee_cis_fraud_detection/week_1/datasets/datasets.md` - 3 подходящих anti-fraud датасета;
- `docs/ieee_cis_fraud_detection/week_1/instructions/eda_sql_checklist.md` - первый рабочий чеклист;
- `docs/ieee_cis_fraud_detection/week_1/datasets/selected_dataset.md` - выбранный датасет и рамки `MVP`;
- `docs/ieee_cis_fraud_detection/week_1/analysis/data_dictionary_ieee_cis_v1.md` - первая версия `data dictionary`;
- `sql/01_base_metrics.sql` - стартовые аналитические запросы;
- `sql/02_suspicious_patterns.sql` - запросы на подозрительные паттерны.

## Ближайший результат

После заполнения этого каркаса у проекта должен появиться первый демонстрационный слой:

- выбранный датасет;
- ноутбук с `EDA`;
- базовые `SQL`-метрики;
- 5-10 антифрод-гипотез;
- описание следующих шагов для признаков и модели.

## API Scoring Examples

The MVP API exposes two endpoints:

- `GET /health`
- `POST /score`

To validate the scoring behavior, I tested three predefined transaction scenarios through the `requests` client.

| Scenario   | Active Signals                                                                                        | Fraud Score | Risk Label | Manual Review |
| ---------- | ----------------------------------------------------------------------------------------------------- | ----------: | ---------- | ------------- |
| Low risk   | No binary risk flags triggered                                                                        |  `0.430693` | `low`      | `false`       |
| Medium-ish | `card6=credit`, high-risk `P_emaildomain`, missing `R_emaildomain`                                    |  `0.667183` | `low`      | `false`       |
| High risk  | `ProductCD=C`, high-risk `R_emaildomain`, `card6=credit`, high-risk `P_emaildomain`, `card4=discover` |  `0.885149` | `high`     | `true`        |

### Interpretation

These examples show that the model behaves consistently with the anti-fraud logic used in the MVP:

- more risk signals lead to a higher `fraud_score`;
- the API does not return only a score, but also a business action through `needs_manual_review`;
- the threshold (`0.7`) converts model output into an operational review decision;
- `active_signals` make the response easier to interpret for a fraud analyst.

This makes the project more than a notebook-based experiment: it demonstrates a working scoring API that can be queried from both Swagger UI and a Python client.
