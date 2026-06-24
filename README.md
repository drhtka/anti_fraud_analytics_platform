# Anti-Fraud Analytics Platform

A portfolio project focused on risk analytics and anti-fraud workflows.

## Project Goal

Demonstrate in one end-to-end case how to:

- work with transactional data;
- perform `SQL` analysis and `EDA`;
- formulate anti-fraud hypotheses;
- build features and a baseline `ML` model;
- explain results in business terms;
- package the solution with `FastAPI`.

## Project Structure

- `data/` - source data notes and local datasets;
- `sql/` - analytical queries and feature marts;
- `notebooks/` - `EDA` and exploratory notebooks;
- `src/` - data preparation, features, rules, and model code;
- `api/` - `FastAPI` app and request/response schemas;
- `docs/` - working materials organized by project and week.

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
2. Create the secrets directory structure if it is still empty:

```bash
mkdir -p secrets
```

3. Put your Google service account key at `secrets/gcp-service-account.json`.
4. Fill in `BIGQUERY_PROJECT_ID`, and optionally adjust `BIGQUERY_DATASET` / `BIGQUERY_TABLE`.

Expected local structure:

```text
.
├── .env
└── secrets/
    ├── .gitignore
    ├── README.md
    └── gcp-service-account.json
```

Minimal `.env` example:

```env
BIGQUERY_PROJECT_ID=your-gcp-project-id
BIGQUERY_DATASET=anti_fraud_analytics
BIGQUERY_TABLE=scoring_events
BIGQUERY_AUTO_CREATE=true
REDIS_SCORE_CACHE_TTL_SECONDS=900
ENABLE_BIGQUERY_EVENT_SINK=true
ENABLE_REDIS_SCORE_CACHE=true
```

### Start Docker Mode

```bash
docker compose up --build
```

### BigQuery Smoke Check Inside Docker

Run this after `.env` and `secrets/gcp-service-account.json` are in place:

```bash
docker compose run --rm app python scripts/bigquery_smoke_check.py
```

If everything is configured correctly, the command prints:

- `BigQuery smoke check passed`
- active `project_id`
- target `dataset`
- target `table`
- `checked_at` timestamp from BigQuery

Then open:

- `http://localhost:8000/`
- `http://localhost:8000/health`
- `http://localhost:8000/ops/status`

### Docker Notes

- `POST /score` stays synchronous and returns immediately from the API process.
- Repeated identical score requests can be served from `Redis`.
- `BigQuery` persistence is offloaded to `Celery`, so the request path is not blocked by warehouse writes.
- If `BigQuery` variables are missing, the API still scores normally, but background export is skipped.
- The `Score` page also shows a live infrastructure status card powered by `GET /ops/status`.

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
