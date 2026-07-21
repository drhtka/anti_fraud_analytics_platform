from __future__ import annotations

import hashlib
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from api.cache import load_cached_score_response, store_cached_score_response
from api.event_sink import enqueue_score_event
from api.i18n import DEFAULT_LANGUAGE, Language, detect_language, translate
from api.model_bundle import ModelBundle, load_model_bundle
from api.runtime_status import build_runtime_status
from api.schemas import (
    ExplainResponse,
    HealthResponse,
    RuntimeStatusResponse,
    ScoreOperationStatus,
    ScoreRequest,
    ScoreResponse,
)
from api.scoring import explain_from_score_response, localize_score_response, score_transaction
from api.settings import DEFAULT_MODEL_ARTIFACT_PATH, get_runtime_settings
from api.ui_content import (
    load_eda_sections,
    load_eda_summary,
    load_ml_content,
    load_score_evidence,
    load_sql_sections,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if get_runtime_settings().runtime_mode == "docker":
        try:
            get_model_bundle()
        except FileNotFoundError:
            pass
    yield


app = FastAPI(
    title="Anti-Fraud Analytics Platform API",
    version="0.1.0",
    description="Week 4 MVP API with /health, /score, and /explain endpoints.",
    lifespan=lifespan,
)

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
NOTEBOOKS_DIR = BASE_DIR / "notebooks"
LOOKER_STUDIO_EMBED_URL = (
    "https://datastudio.google.com/embed/reporting/"
    "6304c4ce-f5cf-4a42-9fa9-7c5640f8c72a/page/iey1F"
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.policies["json.dumps_kwargs"] = {
    **templates.env.policies.get("json.dumps_kwargs", {}),
    "ensure_ascii": False,
}
PAYLOADS_DIR = Path(__file__).resolve().parent / "payloads"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

DEBUG_DEFERRED_TABS_LOG = BASE_DIR / "debug-domain-deferred-tabs.ndjson"
DEBUG_LANGUAGE_SWITCH_LOG = BASE_DIR / "debug-language-switch-lag.ndjson"
DATASET_SOURCE_URL = (
    "https://www.kaggle.com/datasets/lnasiri007/ieeecis-fraud-detection/data"
)
DOWNLOADABLE_DATASETS = {
    "train_identity": {
        "label": "train_identity.csv",
        "path": RAW_DATA_DIR / "train_identity.csv",
    },
    "train_transaction": {
        "label": "train_transaction.csv",
        "path": RAW_DATA_DIR / "train_transaction.csv",
    },
}


@lru_cache(maxsize=1)
def get_model_bundle() -> ModelBundle:
    return load_model_bundle()


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


def format_ui_datetime(value: str | None, lang: Language) -> str:
    if not value:
        return "n/a"

    try:
        parsed_value = datetime.fromisoformat(value)
    except ValueError:
        return value

    month_names = (
        {
            1: "January",
            2: "February",
            3: "March",
            4: "April",
            5: "May",
            6: "June",
            7: "July",
            8: "August",
            9: "September",
            10: "October",
            11: "November",
            12: "December",
        }
        if lang == "en"
        else {
            1: "січня",
            2: "лютого",
            3: "березня",
            4: "квітня",
            5: "травня",
            6: "червня",
            7: "липня",
            8: "серпня",
            9: "вересня",
            10: "жовтня",
            11: "листопада",
            12: "грудня",
        }
    )
    month_label = month_names.get(parsed_value.month, f"{parsed_value.month:02d}")
    if lang == "en":
        return f"{month_label} {parsed_value.day}, {parsed_value.year}, {parsed_value:%H:%M}"
    return f"{parsed_value.day} {month_label} {parsed_value.year}, {parsed_value:%H:%M}"


def get_score_response(request: ScoreRequest) -> tuple[ScoreResponse, str]:
    # region debug-point language-switch-get-score-response
    started_at = perf_counter()
    # endregion debug-point language-switch-get-score-response
    cached_response = load_cached_score_response(request)
    if cached_response is not None:
        # region debug-point language-switch-get-score-response
        append_debug_language_switch_log(
            "server_get_score_response",
            {
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                "score_source": "redis_cache",
                "transaction_id": request.transaction_id,
            },
        )
        # endregion debug-point language-switch-get-score-response
        return cached_response, "redis_cache"

    bundle = get_model_bundle()
    score_response = score_transaction(request=request, bundle=bundle)
    store_cached_score_response(request, score_response)
    # region debug-point language-switch-get-score-response
    append_debug_language_switch_log(
        "server_get_score_response",
        {
            "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            "score_source": "model",
            "transaction_id": request.transaction_id,
        },
    )
    # endregion debug-point language-switch-get-score-response
    return score_response, "model"


def attach_score_operation_status(
    score_response: ScoreResponse,
    score_source: str,
    event_status: str,
    event_sink: str,
    event_id: str | None = None,
) -> ScoreResponse:
    return score_response.model_copy(
        update={
            "operation_status": ScoreOperationStatus(
                runtime_mode=get_runtime_settings().runtime_mode,
                score_source=score_source,
                event_status=event_status,
                event_sink=event_sink,
                event_id=event_id,
                scored_at=datetime.now(timezone.utc).isoformat(),
            )
        }
    )


def build_ui_form_data(request: Request) -> dict[str, str]:
    return {
        "transaction_id": request.query_params.get("transaction_id", ""),
        "transaction_amount": request.query_params.get("transaction_amount", ""),
        "product_cd": request.query_params.get("product_cd", ""),
        "card1": request.query_params.get("card1", ""),
        "card4": request.query_params.get("card4", ""),
        "card6": request.query_params.get("card6", ""),
        "p_emaildomain": request.query_params.get("p_emaildomain", ""),
        "r_emaildomain": request.query_params.get("r_emaildomain", ""),
    }


def has_score_form_input(form_data: dict[str, str]) -> bool:
    return any(value.strip() for value in form_data.values())


def build_score_request(form_data: dict[str, str]) -> ScoreRequest:
    normalized_payload = {
        key: (value if value != "" else None)
        for key, value in form_data.items()
    }
    return ScoreRequest(**normalized_payload)


def build_frontend_i18n(lang: Language) -> dict[str, object]:
    return {
        "scorePlaceholderTitle": translate(
            lang,
            "Готово до демонстрації скорингу",
            "Ready for the scoring demo",
        ),
        "scorePlaceholderIntro": translate(
            lang,
            'Обери один із трьох демо-сценаріїв і натисни кнопку "Виконати скоринг".',
            'Choose one of the three demo scenarios and click "Run scoring".',
        ),
        "scorePlaceholderAfter": translate(
            lang,
            "Після запуску на цій сторінці з'являться:",
            "After running, this page will show:",
        ),
        "scorePlaceholderBullets": [
            translate(lang, "підсумковий fraud score і рівень ризику;", "the final fraud score and risk level;"),
            translate(lang, "рішення щодо ручної перевірки;", "the manual review decision;"),
            translate(lang, "активні ризик-сигнали для транзакції;", "active risk signals for the transaction;"),
            translate(lang, "коротке пояснення результату;", "a short explanation of the result;"),
            translate(
                lang,
                "підтвердження з сирих таблиць для ключових сигналів.",
                "evidence from the raw tables for key signals.",
            ),
        ],
        "loadingTitle": translate(lang, "Завантаження", "Loading"),
        "loadingHintPrefix": translate(
            lang,
            "Рендеримо вміст розділу",
            "Rendering content for",
        ),
        "loadingErrorTitle": translate(lang, "Помилка завантаження", "Loading error"),
        "loadingErrorPrefix": translate(
            lang,
            "Не вдалося завантажити вміст розділу",
            "Failed to load content for",
        ),
        "submitRunning": translate(lang, "Виконуємо скоринг...", "Running scoring..."),
        "submitDefault": translate(lang, "Виконати скоринг", "Run scoring"),
        "screenLabels": {
            "score": translate(lang, "Скоринг", "Scoring"),
            "eda": "EDA",
            "sql": "SQL",
            "ml": "ML",
            "dashboard": translate(lang, "Дашборд", "Dashboard"),
            "json": "JSON",
        },
    }


def load_demo_payloads(lang: Language) -> list[dict[str, object]]:
    payload_specs = [
        (translate(lang, "Високий ризик", "High risk"), "high_risk.json"),
        (translate(lang, "Середній ризик", "Medium risk"), "medium_ish.json"),
        (translate(lang, "Низький ризик", "Low risk"), "low_risk.json"),
    ]
    demo_payloads: list[dict[str, object]] = []

    for label, filename in payload_specs:
        payload_path = PAYLOADS_DIR / filename
        with payload_path.open("r", encoding="utf-8") as file:
            demo_payloads.append(
                {
                    "label": label,
                    "filename": filename,
                    "payload": json.load(file),
                }
            )

    return demo_payloads


def format_file_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024 or unit == "GB":
            if unit == "B":
                return f"{num_bytes} {unit}"
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return "n/a"


def is_ui_translate_request(request: Request) -> bool:
    return request.query_params.get("ui_translate") == "1"


def build_ui_translate_operation_status(
    request: Request,
    score_source: str,
) -> ScoreOperationStatus:
    request_score_source = request.query_params.get("ui_score_source")
    request_event_status = request.query_params.get("ui_event_status")
    request_event_sink = request.query_params.get("ui_event_sink")
    request_event_id = request.query_params.get("ui_event_id")
    request_scored_at = request.query_params.get("ui_scored_at")

    return ScoreOperationStatus(
        runtime_mode=get_runtime_settings().runtime_mode,
        score_source=(
            request_score_source
            if request_score_source in {"model", "redis_cache"}
            else score_source
        ),
        event_status=(
            request_event_status
            if request_event_status in {"queued", "disabled", "failed"}
            else "disabled"
        ),
        event_sink=(
            request_event_sink
            if request_event_sink in {"celery_bigquery", "disabled"}
            else "disabled"
        ),
        event_id=request_event_id or None,
        scored_at=request_scored_at or datetime.now(timezone.utc).isoformat(),
    )


def iter_static_asset_paths() -> list[Path]:
    asset_paths: list[Path] = []

    for asset_dir in (STATIC_DIR / "css", STATIC_DIR / "js"):
        if not asset_dir.exists():
            continue

        asset_paths.extend(
            sorted(path for path in asset_dir.rglob("*") if path.is_file())
        )

    return asset_paths


def get_asset_version() -> str:
    # region debug-point language-switch-asset-version
    started_at = perf_counter()
    # endregion debug-point language-switch-asset-version
    version_fingerprint = hashlib.sha256()

    for path in iter_static_asset_paths():
        stat = path.stat()
        relative_path = path.relative_to(BASE_DIR).as_posix()
        version_fingerprint.update(
            f"{relative_path}:{stat.st_mtime_ns}:{stat.st_size}\n".encode("utf-8")
        )

    version = version_fingerprint.hexdigest()[:16]
    # region debug-point language-switch-asset-version
    append_debug_language_switch_log(
        "server_get_asset_version",
        {
            "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            "asset_count": len(iter_static_asset_paths()),
            "version": version,
        },
    )
    # endregion debug-point language-switch-asset-version
    return version


@lru_cache(maxsize=2)
def get_downloadable_datasets(lang: Language) -> dict[str, dict[str, object]]:
    datasets: dict[str, dict[str, object]] = {}

    for dataset_name, dataset in DOWNLOADABLE_DATASETS.items():
        dataset_path = dataset["path"]
        file_size_bytes = dataset_path.stat().st_size if dataset_path.exists() else 0
        row_count = 0

        if dataset_path.exists():
            with dataset_path.open("r", encoding="utf-8", newline="") as dataset_file:
                row_count = max(sum(1 for _ in dataset_file) - 1, 0)

        datasets[dataset_name] = {
            **dataset,
            "title": (
                translate(lang, "Identity-ознаки", "Identity features")
                if dataset_name == "train_identity"
                else translate(lang, "Транзакції та fraud-мітка", "Transactions and fraud label")
            ),
            "description": (
                translate(
                    lang,
                    "Identity-таблиця з device/browser/user identity ознаками.",
                    "Identity table with device, browser, and user identity features.",
                )
                if dataset_name == "train_identity"
                else translate(
                    lang,
                    "Transaction-таблиця з основними fraud-фічами та цільовою змінною.",
                    "Transaction table with the main fraud features and the target label.",
                )
            ),
            "path_text": str(dataset_path),
            "file_size": format_file_size(file_size_bytes),
            "row_count": row_count,
        }

    return datasets


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    # region debug-point language-switch-index
    request_started_at = perf_counter()
    server_timing: dict[str, float] = {}
    # endregion debug-point language-switch-index
    lang = detect_language(request)
    translate_only = is_ui_translate_request(request)
    tr = lambda uk, en: translate(lang, uk, en)
    form_data = build_ui_form_data(request)
    score_result: ScoreResponse | None = None
    explain_result: ExplainResponse | None = None
    score_evidence_blocks: list[dict[str, object]] = []
    score_evidence_note: str | None = None
    score_result_json: dict[str, object] | None = None
    explain_result_json: dict[str, object] | None = None
    error_message: str | None = None

    if has_score_form_input(form_data):
        try:
            score_request = build_score_request(form_data)
            # region debug-point language-switch-index
            score_started_at = perf_counter()
            # endregion debug-point language-switch-index
            score_result, score_source = get_score_response(score_request)
            # region debug-point language-switch-index
            server_timing["get_score_response_ms"] = round(
                (perf_counter() - score_started_at) * 1000,
                2,
            )
            localize_started_at = perf_counter()
            # endregion debug-point language-switch-index
            score_result = localize_score_response(score_result, lang)
            # region debug-point language-switch-index
            server_timing["localize_score_response_ms"] = round(
                (perf_counter() - localize_started_at) * 1000,
                2,
            )
            # endregion debug-point language-switch-index

            if translate_only:
                score_result = score_result.model_copy(
                    update={
                        "operation_status": build_ui_translate_operation_status(
                            request,
                            score_source=score_source,
                        )
                    }
                )
            else:
                dispatch_result = enqueue_score_event(score_request, score_result)
                score_result = attach_score_operation_status(
                    score_result,
                    score_source=score_source,
                    event_status=dispatch_result.status,
                    event_sink=dispatch_result.sink,
                    event_id=dispatch_result.event_id,
                )

            # region debug-point language-switch-index
            explain_started_at = perf_counter()
            # endregion debug-point language-switch-index
            explain_result = explain_from_score_response(score_result, lang=lang)
            # region debug-point language-switch-index
            server_timing["explain_from_score_response_ms"] = round(
                (perf_counter() - explain_started_at) * 1000,
                2,
            )
            evidence_started_at = perf_counter()
            # endregion debug-point language-switch-index
            score_evidence_blocks = load_score_evidence(
                str(DATA_DIR),
                score_request=score_request,
                feature_values=score_result.feature_values,
                lang=lang,
            )
            # region debug-point language-switch-index
            server_timing["load_score_evidence_ms"] = round(
                (perf_counter() - evidence_started_at) * 1000,
                2,
            )
            # endregion debug-point language-switch-index
            if not score_evidence_blocks:
                score_evidence_note = tr(
                    "Поточні MVP-блоки підтвердження покривають ProductCD, "
                    "email-домени та аномалії суми. Цей запит не активував "
                    "один із підтриманих сигналів із табличним підтвердженням.",
                    "The current MVP evidence blocks cover ProductCD, email domains, "
                    "and amount anomalies. This request did not trigger one of the "
                    "supported signals with tabular evidence.",
                )
            score_result_json = score_result.model_dump(mode="json")
            explain_result_json = explain_result.model_dump(mode="json")
        except FileNotFoundError as exc:
            error_message = str(exc)
        except ValidationError as exc:
            error_message = exc.errors()[0]["msg"]

    # region debug-point language-switch-index
    asset_version_started_at = perf_counter()
    asset_version = get_asset_version()
    server_timing["get_asset_version_ms"] = round(
        (perf_counter() - asset_version_started_at) * 1000,
        2,
    )
    append_debug_language_switch_log(
        "server_index_timing",
        {
            "duration_ms": round((perf_counter() - request_started_at) * 1000, 2),
            "path": str(request.url.path),
            "query": str(request.url.query),
            "lang": lang,
            "translate_only": translate_only,
            "has_score_form_input": has_score_form_input(form_data),
            "error_message": error_message,
            "score_evidence_block_count": len(score_evidence_blocks),
            "timing": server_timing,
        },
    )
    # endregion debug-point language-switch-index
    response = templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "lang": lang,
            "asset_version": asset_version,
            "page_title": tr("Антифрод аналітика та скоринг", "Anti-fraud analytics and scoring"),
            "tr": tr,
            "form_data": form_data,
            "score_result": score_result,
            "explain_result": explain_result,
            "score_evidence_blocks": score_evidence_blocks,
            "score_evidence_note": score_evidence_note,
            "score_result_json": score_result_json,
            "explain_result_json": explain_result_json,
            "error_message": error_message,
            "format_ui_datetime": lambda value: format_ui_datetime(value, lang),
            "demo_payloads": load_demo_payloads(lang),
            "dashboard_embed_url": LOOKER_STUDIO_EMBED_URL,
            "dataset_source_url": DATASET_SOURCE_URL,
            "downloadable_datasets": get_downloadable_datasets(lang),
            "frontend_i18n": build_frontend_i18n(lang),
        },
    )
    response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365, samesite="lax")
    return response


@app.post("/api/debug/deferred-tabs")
async def debug_deferred_tabs(request: Request) -> JSONResponse:
    payload = await request.json()
    DEBUG_DEFERRED_TABS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DEBUG_DEFERRED_TABS_LOG.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return JSONResponse({"ok": True})


@app.get("/ui/eda", response_class=HTMLResponse, name="eda_screen")
def eda_screen(request: Request) -> HTMLResponse:
    lang = detect_language(request)
    response = templates.TemplateResponse(
        request=request,
        name="partials/_eda_screen.html",
        context={
            "lang": lang,
            "tr": lambda uk, en: translate(lang, uk, en),
            "eda_summary": load_eda_summary(str(DATA_DIR), lang=lang),
            "eda_sections": load_eda_sections(str(DATA_DIR), lang=lang),
        },
    )
    response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365, samesite="lax")
    return response


@app.get("/ui/sql", response_class=HTMLResponse, name="sql_screen")
def sql_screen(request: Request) -> HTMLResponse:
    lang = detect_language(request)
    response = templates.TemplateResponse(
        request=request,
        name="partials/_sql_screen.html",
        context={
            "lang": lang,
            "tr": lambda uk, en: translate(lang, uk, en),
            "sql_sections": load_sql_sections(str(DATA_DIR), lang=lang),
        },
    )
    response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365, samesite="lax")
    return response


@app.get("/ui/ml", response_class=HTMLResponse, name="ml_screen")
def ml_screen(request: Request) -> HTMLResponse:
    lang = detect_language(request)
    response = templates.TemplateResponse(
        request=request,
        name="partials/_ml_screen.html",
        context={
            "lang": lang,
            "tr": lambda uk, en: translate(lang, uk, en),
            "ml_content": load_ml_content(str(NOTEBOOKS_DIR / "05_model_comparison.ipynb"), lang=lang),
        },
    )
    response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365, samesite="lax")
    return response


@app.get("/ui/dashboard", response_class=HTMLResponse, name="dashboard_screen")
def dashboard_screen(request: Request) -> HTMLResponse:
    lang = detect_language(request)
    response = templates.TemplateResponse(
        request=request,
        name="partials/_dashboard_screen.html",
        context={
            "lang": lang,
            "tr": lambda uk, en: translate(lang, uk, en),
            "dashboard_embed_url": LOOKER_STUDIO_EMBED_URL,
        },
    )
    response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365, samesite="lax")
    return response


@app.get("/downloads/{dataset_name}", name="download_dataset")
def download_dataset(dataset_name: str) -> FileResponse:
    dataset = DOWNLOADABLE_DATASETS.get(dataset_name)

    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    dataset_path = dataset["path"]

    if not isinstance(dataset_path, Path) or not dataset_path.exists():
        raise HTTPException(status_code=404, detail="Dataset file is missing.")

    return FileResponse(
        path=dataset_path,
        filename=dataset["label"],
        media_type="text/csv",
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_runtime_settings()
    try:
        bundle = get_model_bundle()
    except FileNotFoundError:
        return HealthResponse(
            status="degraded",
            ready_for_scoring=False,
            artifact_path=str(DEFAULT_MODEL_ARTIFACT_PATH),
            runtime_mode=settings.runtime_mode,
            redis_score_cache_enabled=settings.redis_score_cache_enabled,
            bigquery_event_sink_enabled=settings.celery_event_sink_enabled,
            bigquery_configured=settings.bigquery_configured,
        )

    return HealthResponse(
        status="ok",
        ready_for_scoring=True,
        model_name=bundle.model_name,
        model_version=bundle.model_version,
        artifact_path=str(DEFAULT_MODEL_ARTIFACT_PATH),
        runtime_mode=settings.runtime_mode,
        redis_score_cache_enabled=settings.redis_score_cache_enabled,
        bigquery_event_sink_enabled=settings.celery_event_sink_enabled,
        bigquery_configured=settings.bigquery_configured,
    )


@app.get("/ops/status", response_model=RuntimeStatusResponse, name="ops_status")
def ops_status() -> RuntimeStatusResponse:
    return build_runtime_status()


@app.post("/score", response_model=ScoreResponse)
def score(request: ScoreRequest, lang: Language = DEFAULT_LANGUAGE) -> ScoreResponse:
    try:
        score_response, score_source = get_score_response(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    score_response = localize_score_response(score_response, lang)
    dispatch_result = enqueue_score_event(request, score_response)
    return attach_score_operation_status(
        score_response,
        score_source=score_source,
        event_status=dispatch_result.status,
        event_sink=dispatch_result.sink,
        event_id=dispatch_result.event_id,
    )


@app.post("/explain", response_model=ExplainResponse)
def explain(request: ScoreRequest, lang: Language = DEFAULT_LANGUAGE) -> ExplainResponse:
    try:
        score_response, score_source = get_score_response(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    score_response = localize_score_response(score_response, lang)
    dispatch_result = enqueue_score_event(request, score_response)
    score_response = attach_score_operation_status(
        score_response,
        score_source=score_source,
        event_status=dispatch_result.status,
        event_sink=dispatch_result.sink,
        event_id=dispatch_result.event_id,
    )
    return explain_from_score_response(score_response, lang=lang)
