from __future__ import annotations

import math

import pandas as pd

from api.i18n import DEFAULT_LANGUAGE, Language, translate
from api.model_bundle import ModelBundle
from api.schemas import ExplainResponse, ScoreRequest, ScoreResponse

SIGNAL_FALLBACK_KEY = "__no_binary_risk_signals__"


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


def get_signal_label(feature_name: str, lang: Language) -> str:
    labels = {
        "feat_productcd_c_flag": ("ProductCD = C", "ProductCD = C"),
        "feat_high_risk_r_email_flag": (
            "R_emaildomain входить до списку доменів високого ризику",
            "R_emaildomain belongs to the high-risk domain list",
        ),
        "feat_card6_credit_flag": ("card6 = credit", "card6 = credit"),
        "feat_high_risk_p_email_flag": (
            "P_emaildomain входить до списку доменів високого ризику",
            "P_emaildomain belongs to the high-risk domain list",
        ),
        "feat_card4_discover_flag": ("card4 = discover", "card4 = discover"),
        "feat_missing_r_email_flag": ("R_emaildomain відсутній", "R_emaildomain is missing"),
        "feat_amount_gt_card1_avg_plus_3std": (
            "Сума транзакції перевищує середнє для card1 + 3 std",
            "Transaction amount exceeds the card1 average + 3 std",
        ),
    }
    uk, en = labels[feature_name]
    return translate(lang, uk, en)


def get_no_signal_message(lang: Language) -> str:
    return translate(
        lang,
        "Для поточного запиту не спрацювали бінарні ризик-сигнали",
        "No binary risk signals were triggered for the current request",
    )


def build_active_signals(feature_values: dict[str, float], lang: Language) -> list[str]:
    signals = [
        get_signal_label(feature_name, lang)
        for feature_name, value in feature_values.items()
        if feature_name != SIGNAL_FALLBACK_KEY and feature_name.startswith("feat_") and value >= 1.0
        and feature_name
        in {
            "feat_productcd_c_flag",
            "feat_high_risk_r_email_flag",
            "feat_card6_credit_flag",
            "feat_high_risk_p_email_flag",
            "feat_card4_discover_flag",
            "feat_missing_r_email_flag",
            "feat_amount_gt_card1_avg_plus_3std",
        }
    ]
    return signals or [get_no_signal_message(lang)]


def resolve_risk_label(fraud_score: float, threshold: float) -> str:
    if fraud_score >= max(threshold + 0.15, 0.85):
        return "high"
    if fraud_score >= threshold:
        return "medium"
    return "low"


def score_transaction(
    request: ScoreRequest,
    bundle: ModelBundle,
    lang: Language = DEFAULT_LANGUAGE,
) -> ScoreResponse:
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
        active_signals=build_active_signals(feature_values, lang),
        feature_values=feature_values,
    )


def localize_score_response(score_response: ScoreResponse, lang: Language) -> ScoreResponse:
    return score_response.model_copy(
        update={
            "active_signals": build_active_signals(score_response.feature_values, lang),
        }
    )


def build_explanation_points(score_response: ScoreResponse, lang: Language) -> list[str]:
    explanation_points = [
        translate(
            lang,
            f"Модель повернула fraud_score={score_response.fraud_score}, а поріг рішення дорівнює {score_response.threshold_used}.",
            f"The model returned fraud_score={score_response.fraud_score}, and the decision threshold is {score_response.threshold_used}.",
        ),
    ]

    if score_response.needs_manual_review:
        explanation_points.append(
            translate(
                lang,
                "Транзакція перевищує поточний поріг рішення і має бути відправлена на ручну перевірку.",
                "The transaction exceeds the current decision threshold and should be sent for manual review.",
            )
        )
    else:
        explanation_points.append(
            translate(
                lang,
                "Транзакція нижче поточного порогу рішення і не потребує ручної перевірки.",
                "The transaction is below the current decision threshold and does not require manual review.",
            )
        )

    if score_response.active_signals == [get_no_signal_message(lang)]:
        explanation_points.append(
            translate(
                lang,
                "Бінарні ризик-сигнали не спрацювали, тому score переважно формується базовим патерном моделі.",
                "Binary risk signals did not trigger, so the score is mostly driven by the model's base pattern.",
            )
        )
    else:
        explanation_points.append(
            translate(
                lang,
                "Найпомітніші видимі фактори походять з активних бінарних ризик-сигналів, які повернув API.",
                "The most visible factors come from the active binary risk signals returned by the API.",
            )
        )
        explanation_points.extend(
            [
                translate(lang, f"Активний сигнал: {signal}.", f"Active signal: {signal}.")
                for signal in score_response.active_signals
            ]
        )

    return explanation_points


def build_explanation_text(score_response: ScoreResponse, lang: Language) -> str:
    if score_response.needs_manual_review:
        review_sentence = translate(
            lang,
            "Цю транзакцію слід направити на ручну перевірку.",
            "This transaction should be sent for manual review.",
        )
    else:
        review_sentence = translate(
            lang,
            "Ця транзакція залишається нижче порогу ручної перевірки.",
            "This transaction remains below the manual review threshold.",
        )

    signal_summary = (
        translate(
            lang,
            "Бінарні ризик-сигнали не спрацювали.",
            "Binary risk signals did not trigger.",
        )
        if score_response.active_signals == [get_no_signal_message(lang)]
        else translate(
            lang,
            f"Спрацювали сигнали: {', '.join(score_response.active_signals)}.",
            f"Triggered signals: {', '.join(score_response.active_signals)}.",
        )
    )

    return translate(
        lang,
        f"Модель сформувала fraud_score={score_response.fraud_score} "
        f"при threshold={score_response.threshold_used}, тому risk_label={score_response.risk_label}. "
        f"{review_sentence} {signal_summary}",
        f"The model produced fraud_score={score_response.fraud_score} "
        f"with threshold={score_response.threshold_used}, so risk_label={score_response.risk_label}. "
        f"{review_sentence} {signal_summary}",
    )


def explain_from_score_response(
    score_response: ScoreResponse,
    lang: Language = DEFAULT_LANGUAGE,
) -> ExplainResponse:
    localized_score_response = localize_score_response(score_response, lang)
    return ExplainResponse(
        transaction_id=localized_score_response.transaction_id,
        fraud_score=localized_score_response.fraud_score,
        threshold_used=localized_score_response.threshold_used,
        risk_label=localized_score_response.risk_label,
        needs_manual_review=localized_score_response.needs_manual_review,
        model_name=localized_score_response.model_name,
        model_version=localized_score_response.model_version,
        active_signals=localized_score_response.active_signals,
        explanation_text=build_explanation_text(localized_score_response, lang),
        explanation_points=build_explanation_points(localized_score_response, lang),
        feature_values=localized_score_response.feature_values,
        operation_status=localized_score_response.operation_status,
    )


def explain_transaction(
    request: ScoreRequest,
    bundle: ModelBundle,
    lang: Language = DEFAULT_LANGUAGE,
) -> ExplainResponse:
    score_response = score_transaction(request=request, bundle=bundle, lang=lang)
    return explain_from_score_response(score_response, lang=lang)
