from __future__ import annotations

import json
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from api.cache import load_cached_score_response, store_cached_score_response
from api.event_sink import enqueue_score_event
from api.model_bundle import ModelBundle, load_model_bundle
from api.runtime_status import build_runtime_status
from api.schemas import (
    ExplainResponse,
    HealthResponse,
    RuntimeStatusResponse,
    ScoreRequest,
    ScoreResponse,
)
from api.scoring import explain_from_score_response, score_transaction
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
NOTEBOOKS_DIR = BASE_DIR / "notebooks"
LOOKER_STUDIO_EMBED_URL = (
    "https://datastudio.google.com/embed/reporting/"
    "6304c4ce-f5cf-4a42-9fa9-7c5640f8c72a/page/iey1F"
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
PAYLOADS_DIR = Path(__file__).resolve().parent / "payloads"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@lru_cache(maxsize=1)
def get_model_bundle() -> ModelBundle:
    return load_model_bundle()


def get_score_response(request: ScoreRequest) -> ScoreResponse:
    cached_response = load_cached_score_response(request)
    if cached_response is not None:
        return cached_response

    bundle = get_model_bundle()
    score_response = score_transaction(request=request, bundle=bundle)
    store_cached_score_response(request, score_response)
    return score_response


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


def build_score_request(form_data: dict[str, str]) -> ScoreRequest:
    normalized_payload = {
        key: (value if value != "" else None)
        for key, value in form_data.items()
    }
    return ScoreRequest(**normalized_payload)


def load_demo_payloads() -> list[dict[str, object]]:
    payload_specs = [
        ("Високий ризик", "high_risk.json"),
        ("Середній ризик", "medium_ish.json"),
        ("Низький ризик", "low_risk.json"),
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


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    form_data = build_ui_form_data(request)
    score_result: ScoreResponse | None = None
    explain_result: ExplainResponse | None = None
    score_evidence_blocks: list[dict[str, object]] = []
    score_evidence_note: str | None = None
    score_result_json: dict[str, object] | None = None
    explain_result_json: dict[str, object] | None = None
    error_message: str | None = None

    if request.query_params:
        try:
            score_request = build_score_request(form_data)
            score_result = get_score_response(score_request)
            explain_result = explain_from_score_response(score_result)
            score_evidence_blocks = load_score_evidence(
                str(DATA_DIR),
                score_request=score_request,
                feature_values=score_result.feature_values,
            )
            if not score_evidence_blocks:
                score_evidence_note = (
                    "Поточні MVP-блоки підтвердження покривають ProductCD, "
                    "email-домени та аномалії суми. Цей запит не активував "
                    "один із підтриманих сигналів із табличним підтвердженням."
                )
            score_result_json = score_result.model_dump(mode="json")
            explain_result_json = explain_result.model_dump(mode="json")
        except FileNotFoundError as exc:
            error_message = str(exc)
        except ValidationError as exc:
            error_message = exc.errors()[0]["msg"]

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "page_title": "Антифрод аналітика та скоринг",
            "form_data": form_data,
            "score_result": score_result,
            "explain_result": explain_result,
            "score_evidence_blocks": score_evidence_blocks,
            "score_evidence_note": score_evidence_note,
            "score_result_json": score_result_json,
            "explain_result_json": explain_result_json,
            "error_message": error_message,
            "demo_payloads": load_demo_payloads(),
            "dashboard_embed_url": LOOKER_STUDIO_EMBED_URL,
        },
    )


@app.get("/ui/eda", response_class=HTMLResponse, name="eda_screen")
def eda_screen(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="partials/_eda_screen.html",
        context={
            "eda_summary": load_eda_summary(str(DATA_DIR)),
            "eda_sections": load_eda_sections(str(DATA_DIR)),
        },
    )


@app.get("/ui/sql", response_class=HTMLResponse, name="sql_screen")
def sql_screen(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="partials/_sql_screen.html",
        context={
            "sql_sections": load_sql_sections(str(DATA_DIR)),
        },
    )


@app.get("/ui/ml", response_class=HTMLResponse, name="ml_screen")
def ml_screen(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="partials/_ml_screen.html",
        context={
            "ml_content": load_ml_content(str(NOTEBOOKS_DIR / "05_model_comparison.ipynb")),
        },
    )


@app.get("/ui/dashboard", response_class=HTMLResponse, name="dashboard_screen")
def dashboard_screen(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="partials/_dashboard_screen.html",
        context={
            "dashboard_embed_url": LOOKER_STUDIO_EMBED_URL,
        },
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
def score(request: ScoreRequest) -> ScoreResponse:
    try:
        score_response = get_score_response(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    enqueue_score_event(request, score_response)
    return score_response


@app.post("/explain", response_model=ExplainResponse)
def explain(request: ScoreRequest) -> ExplainResponse:
    try:
        score_response = get_score_response(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return explain_from_score_response(score_response)
