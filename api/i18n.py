from __future__ import annotations

from typing import Literal

from fastapi import Request

Language = Literal["uk", "en"]

DEFAULT_LANGUAGE: Language = "en"
SUPPORTED_LANGUAGES: set[str] = {"uk", "en"}


def normalize_language(value: str | None) -> Language:
    if value in SUPPORTED_LANGUAGES:
        return value
    return DEFAULT_LANGUAGE


def detect_language(request: Request) -> Language:
    query_lang = request.query_params.get("lang")
    if query_lang in SUPPORTED_LANGUAGES:
        return query_lang

    cookie_lang = request.cookies.get("lang")
    if cookie_lang in SUPPORTED_LANGUAGES:
        return cookie_lang

    accept_language = request.headers.get("accept-language", "").lower()
    if accept_language.startswith("en"):
        return "en"

    return DEFAULT_LANGUAGE


def translate(lang: Language, uk: str, en: str) -> str:
    return en if lang == "en" else uk
