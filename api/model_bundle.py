from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib

from api.settings import DEFAULT_MODEL_ARTIFACT_PATH


@dataclass(slots=True)
class ModelBundle:
    model: Any
    feature_cols: list[str]
    threshold: float
    model_name: str
    model_version: str
    high_risk_p_domains: set[str]
    high_risk_r_domains: set[str]
    card1_amt_mean: dict[int, float]
    card1_amt_std: dict[int, float]


def build_model_bundle(payload: dict[str, Any]) -> ModelBundle:
    return ModelBundle(
        model=payload["model"],
        feature_cols=list(payload["feature_cols"]),
        threshold=float(payload["threshold"]),
        model_name=str(payload["model_name"]),
        model_version=str(payload["model_version"]),
        high_risk_p_domains={str(value).lower() for value in payload["high_risk_p_domains"]},
        high_risk_r_domains={str(value).lower() for value in payload["high_risk_r_domains"]},
        card1_amt_mean={int(key): float(value) for key, value in payload["card1_amt_mean"].items()},
        card1_amt_std={int(key): float(value) for key, value in payload["card1_amt_std"].items()},
    )


def load_model_bundle(path: Path | None = None) -> ModelBundle:
    artifact_path = path or DEFAULT_MODEL_ARTIFACT_PATH

    if not artifact_path.exists():
        raise FileNotFoundError(
            f"Model artifact was not found at {artifact_path}. "
            "Run `python -m api.export_mvp_artifact` first."
        )

    payload = joblib.load(artifact_path)
    return build_model_bundle(payload)
