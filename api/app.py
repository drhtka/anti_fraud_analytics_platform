from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from api.model_bundle import ModelBundle, load_model_bundle
from api.schemas import ExplainResponse, HealthResponse, ScoreRequest, ScoreResponse
from api.scoring import explain_transaction, score_transaction
from api.settings import DEFAULT_MODEL_ARTIFACT_PATH
from api.ui_content import load_eda_sections, load_sql_sections


app = FastAPI(
    title="Anti-Fraud Analytics Platform API",
    version="0.1.0",
    description="Week 4 MVP API with /health, /score, and /explain endpoints.",
)

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
PAYLOADS_DIR = Path(__file__).resolve().parent / "payloads"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@lru_cache(maxsize=1)
def get_model_bundle() -> ModelBundle:
    return load_model_bundle()


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
        ("High Risk", "high_risk.json"),
        ("Medium-ish", "medium_ish.json"),
        ("Low Risk", "low_risk.json"),
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
    score_result_json: dict[str, object] | None = None
    explain_result_json: dict[str, object] | None = None
    error_message: str | None = None

    if request.query_params:
        try:
            score_request = build_score_request(form_data)
            bundle = get_model_bundle()
            score_result = score_transaction(request=score_request, bundle=bundle)
            explain_result = explain_transaction(request=score_request, bundle=bundle)
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
            "page_title": "Anti-Fraud Analytics Platform",
            "form_data": form_data,
            "score_result": score_result,
            "explain_result": explain_result,
            "score_result_json": score_result_json,
            "explain_result_json": explain_result_json,
            "error_message": error_message,
            "demo_payloads": load_demo_payloads(),
            "eda_sections": load_eda_sections(str(DATA_DIR)),
            "sql_sections": load_sql_sections(str(DATA_DIR)),
        },
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        bundle = get_model_bundle()
    except FileNotFoundError:
        return HealthResponse(
            status="degraded",
            ready_for_scoring=False,
            artifact_path=str(DEFAULT_MODEL_ARTIFACT_PATH),
        )

    return HealthResponse(
        status="ok",
        ready_for_scoring=True,
        model_name=bundle.model_name,
        model_version=bundle.model_version,
        artifact_path=str(DEFAULT_MODEL_ARTIFACT_PATH),
    )


@app.post("/score", response_model=ScoreResponse)
def score(request: ScoreRequest) -> ScoreResponse:
    try:
        bundle = get_model_bundle()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return score_transaction(request=request, bundle=bundle)


@app.post("/explain", response_model=ExplainResponse)
def explain(request: ScoreRequest) -> ExplainResponse:
    try:
        bundle = get_model_bundle()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return explain_transaction(request=request, bundle=bundle)
