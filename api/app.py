from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from api.model_bundle import ModelBundle, load_model_bundle
from api.schemas import ExplainResponse, HealthResponse, ScoreRequest, ScoreResponse
from api.scoring import explain_transaction, score_transaction
from api.settings import DEFAULT_MODEL_ARTIFACT_PATH


app = FastAPI(
    title="Anti-Fraud Analytics Platform API",
    version="0.1.0",
    description="Week 4 MVP API with /health, /score, and /explain endpoints.",
)

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@lru_cache(maxsize=1)
def get_model_bundle() -> ModelBundle:
    return load_model_bundle()


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "page_title": "Anti-Fraud Analytics Platform",
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
