"""Centralized LLM factory — picks provider from LLM_PROVIDER env."""
from __future__ import annotations

from typing import Any, Literal

from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)

Provider = Literal["ollama", "groq", "gemini"]


def _make_ollama(temperature: float) -> Any:
    from langchain_ollama import ChatOllama

    cfg = get_settings()
    logger.info("Factory → Ollama (%s)", cfg.OLLAMA_MODEL)
    return ChatOllama(
        base_url=cfg.OLLAMA_BASE_URL,
        model=cfg.OLLAMA_MODEL,
        temperature=temperature,
    )


def _make_groq(temperature: float) -> Any:
    from langchain_groq import ChatGroq

    cfg = get_settings()
    if not cfg.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set")
    logger.info("Factory → Groq (%s)", cfg.GROQ_MODEL)
    return ChatGroq(
        model=cfg.GROQ_MODEL,
        groq_api_key=cfg.GROQ_API_KEY,
        temperature=temperature,
    )


def _make_gemini(temperature: float) -> Any:
    from langchain_google_genai import ChatGoogleGenerativeAI

    cfg = get_settings()
    if not cfg.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set")
    logger.info("Factory → Gemini (%s)", cfg.GEMINI_MODEL)
    return ChatGoogleGenerativeAI(
        model=cfg.GEMINI_MODEL,
        google_api_key=cfg.GEMINI_API_KEY,
        temperature=temperature,
    )


_BUILDERS = {
    "ollama": _make_ollama,
    "groq": _make_groq,
    "gemini": _make_gemini,
}


def get_llm(purpose: str = "default", temperature: float = 0.7) -> Any:
    """
    Return a chat model for the configured LLM_PROVIDER.

    purpose is reserved for future per-role overrides (router/tools/chat);
    today everything uses LLM_PROVIDER.
    """
    cfg = get_settings()
    provider = (cfg.LLM_PROVIDER or "ollama").strip().lower()
    if provider not in _BUILDERS:
        logger.warning("Unknown LLM_PROVIDER=%r — falling back to ollama", provider)
        provider = "ollama"

    try:
        return _BUILDERS[provider](temperature)
    except Exception as e:
        if provider == "ollama":
            raise
        logger.warning(
            "LLM_PROVIDER=%s failed (%s) — falling back to Ollama", provider, e
        )
        return _make_ollama(temperature)
