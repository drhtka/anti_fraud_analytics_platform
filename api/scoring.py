from __future__ import annotations

import math

import pandas as pd

from api.model_bundle import ModelBundle
from api.schemas import ScoreRequest, ScoreResponse


SIGNAL_LABELS = {
    "feat_productcd_c_flag": "ProductCD is C",
    "feat_high_risk_r_email_flag": "R_emaildomain is in the high-risk domain list",
    "feat_card6_credit_flag": "card6 is credit",
    "feat_high_risk_p_email_flag": "P_emaildomain is in the high-risk domain list",
    "feat_card4_discover_flag": "card4 is discover",
    "feat_missing_r_email_flag": "R_emaildomain is missing",
    "feat_amount_gt_card1_avg_plus_3std": "Transaction amount is above the card1 mean plus 3 std",
}


def normalize_string(value: str | None) -> str | None:
    if value is None:
        return None

    stripped = value.strip().lower()
    return stripped or None


def get_card1_threshold(bundle: ModelBundle, card1: int) -> float | None:
    mean_value = bundle.card1_amt_mean.get(card1)
    std_value = bundle.card1_amt_std.get(card1)

    if mean_value is None:
        return None

    return mean_value + 3 * (std_value or 0.0)


def build_feature_values(request: ScoreRequest, bundle: ModelBundle) -> dict[str, float]:
    product_cd = request.product_cd.strip().upper()
    card4 = normalize_string(request.card4)
    card6 = normalize_string(request.card6)
    p_emaildomain = normalize_string(request.p_emaildomain)
    r_emaildomain = normalize_string(request.r_emaildomain)
    card1_threshold = get_card1_threshold(bundle, request.card1)

    feature_values = {
        "feat_productcd_c_flag": float(product_cd == "C"),
        "feat_high_risk_r_email_flag": float(r_emaildomain in bundle.high_risk_r_domains),
        "feat_card6_credit_flag": float(card6 == "credit"),
        "feat_high_risk_p_email_flag": float(p_emaildomain in bundle.high_risk_p_domains),
        "feat_card4_discover_flag": float(card4 == "discover"),
        "feat_missing_r_email_flag": float(r_emaildomain is None),
        "feat_amount_log1p": float(math.log1p(request.transaction_amount)),
        "feat_amount_gt_card1_avg_plus_3std": float(
            card1_threshold is not None and request.transaction_amount > card1_threshold
        ),
    }

    return {feature_name: float(feature_values[feature_name]) for feature_name in bundle.feature_cols}


def build_active_signals(feature_values: dict[str, float]) -> list[str]:
    signals = [
        SIGNAL_LABELS[feature_name]
        for feature_name, value in feature_values.items()
        if feature_name in SIGNAL_LABELS and value >= 1.0
    ]
    return signals or ["No binary risk flags were triggered by the current request"]


def resolve_risk_label(fraud_score: float, threshold: float) -> str:
    if fraud_score >= max(threshold + 0.15, 0.85):
        return "high"
    if fraud_score >= threshold:
        return "medium"
    return "low"


def score_transaction(request: ScoreRequest, bundle: ModelBundle) -> ScoreResponse:
    feature_values = build_feature_values(request, bundle)
    feature_frame = pd.DataFrame([feature_values], columns=bundle.feature_cols)
    fraud_score = float(bundle.model.predict_proba(feature_frame)[0, 1])
    threshold_used = float(request.threshold if request.threshold is not None else bundle.threshold)
    needs_manual_review = fraud_score >= threshold_used

    return ScoreResponse(
        transaction_id=request.transaction_id,
        fraud_score=round(fraud_score, 6),
        threshold_used=threshold_used,
        risk_label=resolve_risk_label(fraud_score, threshold_used),
        needs_manual_review=needs_manual_review,
        model_name=bundle.model_name,
        model_version=bundle.model_version,
        active_signals=build_active_signals(feature_values),
        feature_values=feature_values,
    )
