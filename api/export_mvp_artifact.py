from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split

from api.settings import ARTIFACTS_DIR, DEFAULT_MODEL_ARTIFACT_PATH, PROJECT_ROOT


TRANSACTION_PATH = PROJECT_ROOT / "data" / "train_transaction.csv"
DEFAULT_THRESHOLD = 0.7
HIGH_RISK_P_DOMAINS = {"outlook.com"}
HIGH_RISK_R_DOMAINS = {"outlook.com", "icloud.com", "gmail.com"}
FEATURE_COLS = [
    "feat_productcd_c_flag",
    "feat_high_risk_r_email_flag",
    "feat_card6_credit_flag",
    "feat_high_risk_p_email_flag",
    "feat_card4_discover_flag",
    "feat_missing_r_email_flag",
    "feat_amount_log1p",
    "feat_amount_gt_card1_avg_plus_3std",
]
REQUIRED_COLUMNS = [
    "isFraud",
    "TransactionAmt",
    "ProductCD",
    "card1",
    "card4",
    "card6",
    "P_emaildomain",
    "R_emaildomain",
]


def require_transaction_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing dataset file: {path}. "
            "Create `data/` and place `train_transaction.csv` there first."
        )

    transactions = pd.read_csv(path, usecols=REQUIRED_COLUMNS)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in transactions.columns]

    if missing_columns:
        raise ValueError(f"Dataset is missing required columns: {missing_columns}")

    return transactions


def build_feature_frame(transactions: pd.DataFrame) -> pd.DataFrame:
    feature_df = transactions.copy()
    feature_df["feat_productcd_c_flag"] = (feature_df["ProductCD"] == "C").astype(int)
    feature_df["feat_card4_discover_flag"] = (feature_df["card4"] == "discover").astype(int)
    feature_df["feat_card6_credit_flag"] = (feature_df["card6"] == "credit").astype(int)
    feature_df["feat_high_risk_p_email_flag"] = feature_df["P_emaildomain"].isin(HIGH_RISK_P_DOMAINS).astype(int)
    feature_df["feat_high_risk_r_email_flag"] = feature_df["R_emaildomain"].isin(HIGH_RISK_R_DOMAINS).astype(int)
    feature_df["feat_missing_r_email_flag"] = feature_df["R_emaildomain"].isna().astype(int)
    feature_df["feat_amount_log1p"] = np.log1p(feature_df["TransactionAmt"])
    return feature_df


def add_card1_amount_signal(
    train_df: pd.DataFrame,
    valid_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[int, float], dict[int, float]]:
    card1_amount_stats = (
        train_df.groupby("card1")["TransactionAmt"]
        .agg(card1_amt_mean="mean", card1_amt_std="std")
    )

    train_df = train_df.join(card1_amount_stats, on="card1").copy()
    valid_df = valid_df.join(card1_amount_stats, on="card1").copy()

    for current_df in (train_df, valid_df):
        # The threshold is derived from train-only card statistics to keep inference consistent.
        current_threshold = current_df["card1_amt_mean"] + 3 * current_df["card1_amt_std"].fillna(0)
        current_df["feat_amount_gt_card1_avg_plus_3std"] = (
            current_df["TransactionAmt"] > current_threshold
        ).astype(int)

    card1_amt_mean = {
        int(key): float(value)
        for key, value in card1_amount_stats["card1_amt_mean"].dropna().to_dict().items()
    }
    card1_amt_std = {
        int(key): float(value)
        for key, value in card1_amount_stats["card1_amt_std"].fillna(0).to_dict().items()
    }

    return train_df, valid_df, card1_amt_mean, card1_amt_std


def collect_validation_metrics(
    model: RandomForestClassifier,
    x_valid: pd.DataFrame,
    y_valid: pd.Series,
    threshold: float,
) -> dict[str, float]:
    fraud_scores = model.predict_proba(x_valid)[:, 1]
    predictions = (fraud_scores >= threshold).astype(int)

    return {
        "threshold": threshold,
        "precision": round(float(precision_score(y_valid, predictions, zero_division=0)), 6),
        "recall": round(float(recall_score(y_valid, predictions, zero_division=0)), 6),
        "f1": round(float(f1_score(y_valid, predictions, zero_division=0)), 6),
        "roc_auc": round(float(roc_auc_score(y_valid, fraud_scores)), 6),
    }


def main() -> int:
    transactions = require_transaction_data(TRANSACTION_PATH)
    feature_df = build_feature_frame(transactions)

    train_df, valid_df = train_test_split(
        feature_df,
        test_size=0.2,
        random_state=42,
        stratify=feature_df["isFraud"],
    )

    train_df, valid_df, card1_amt_mean, card1_amt_std = add_card1_amount_signal(
        train_df=train_df,
        valid_df=valid_df,
    )

    x_train = train_df[FEATURE_COLS].copy()
    x_valid = valid_df[FEATURE_COLS].copy()
    y_train = train_df["isFraud"].copy()
    y_valid = valid_df["isFraud"].copy()

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=20,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced_subsample",
    )
    model.fit(x_train, y_train)

    artifact_payload = {
        "model": model,
        "feature_cols": FEATURE_COLS,
        "threshold": DEFAULT_THRESHOLD,
        "model_name": "RandomForestClassifier",
        "model_version": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "high_risk_p_domains": sorted(HIGH_RISK_P_DOMAINS),
        "high_risk_r_domains": sorted(HIGH_RISK_R_DOMAINS),
        "card1_amt_mean": card1_amt_mean,
        "card1_amt_std": card1_amt_std,
        "validation_metrics": collect_validation_metrics(
            model=model,
            x_valid=x_valid,
            y_valid=y_valid,
            threshold=DEFAULT_THRESHOLD,
        ),
    }

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact_payload, DEFAULT_MODEL_ARTIFACT_PATH)

    print(f"Saved model artifact: {DEFAULT_MODEL_ARTIFACT_PATH}")
    print(f"Validation metrics: {artifact_payload['validation_metrics']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
