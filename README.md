# Anti-Fraud Analytics Platform

Портфельный проект под вакансию в аналитике, рисках и антифроде.

## Цель проекта

Показать на одном кейсе:

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

## Local Data

Large `IEEE-CIS` CSV files are kept locally and are not committed to GitHub.

Put the raw files here:

- `data/raw/train_transaction.csv`
- `data/raw/train_identity.csv`

The current MVP UI reads these files on the backend through `DuckDB` and only
renders small result tables, summaries, and charts in the browser.

The current UI is still server-rendered through `FastAPI` templates, while the
target dedicated frontend stack for the project is `SvelteKit`.

To precompute the heavier `EDA` and `SQL` UI cache before starting the server:

```bash
.venv/bin/python scripts/precompute_ui_cache.py
```

## Runtime Modes

The project now supports two infrastructure modes:

- `local` - default mode, no `Celery`, no `Redis`, no `BigQuery`; scoring stays synchronous inside `FastAPI`.
- `docker` - container mode with `Redis` response cache and background `Celery` worker that pushes scoring events into `BigQuery`.

If you run the app locally outside Docker, nothing changes: you can keep using the existing local workflow without queue or cache infrastructure.

## Docker Stack

The Docker stack is designed for the heavier demo mode:

- `app` - `FastAPI` scoring API and server-rendered UI;
- `redis` - cache for repeated `/score` requests;
- `worker` - `Celery` worker that writes score events into `BigQuery` asynchronously.

### Prepare BigQuery Credentials

1. Copy `.env.docker.example` to `.env`.
2. Put your Google service account key at `secrets/gcp-service-account.json`.
3. Fill in `BIGQUERY_PROJECT_ID`, and optionally adjust `BIGQUERY_DATASET` / `BIGQUERY_TABLE`.

### Start Docker Mode

```bash
docker compose up --build
```

Then open:

- `http://localhost:8000/`
- `http://localhost:8000/health`

### Docker Notes

- `POST /score` stays synchronous and returns immediately from the API process.
- Repeated identical score requests can be served from `Redis`.
- `BigQuery` persistence is offloaded to `Celery`, so the request path is not blocked by warehouse writes.
- If `BigQuery` variables are missing, the API still scores normally, but background export is skipped.

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
