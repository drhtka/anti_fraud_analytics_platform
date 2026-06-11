from __future__ import annotations

from pathlib import Path


API_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = API_DIR.parent
ARTIFACTS_DIR = API_DIR / "artifacts"
DEFAULT_MODEL_ARTIFACT_PATH = ARTIFACTS_DIR / "random_forest_mvp.joblib"
