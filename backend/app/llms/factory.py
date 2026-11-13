"""Centralized LLM factory — picks provider from LLM_PROVIDER env."""
from __future__ import annotations

from typing import Any, Literal

from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)

Provider = Literal["ollama", "groq", "gemini"]


def _make_ollama(temperature: float, purpose: str = "default") -> Any:
    from langchain_ollama import ChatOllama

    cfg = get_settings()
    logger.info("Factory → Ollama (%s) [purpose=%s]", cfg.OLLAMA_MODEL, purpose)
    return ChatOllama(
        base_url=cfg.OLLAMA_BASE_URL,
        model=cfg.OLLAMA_MODEL,
        temperature=temperature,
    )


def _make_groq(temperature: float, purpose: str = "default") -> Any:
    from langchain_groq import ChatGroq

    cfg = get_settings()
    if not cfg.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set")

    if purpose in ("research", "coder"):
        model_name = getattr(cfg, "GROQ_RESEARCH_MODEL", None) or cfg.GROQ_MODEL
    else:
        model_name = getattr(cfg, "GROQ_CHAT_MODEL", None) or cfg.GROQ_MODEL

    logger.info("Factory → Groq (%s) [purpose=%s]", model_name, purpose)
    return ChatGroq(
        model=model_name,
        groq_api_key=cfg.GROQ_API_KEY,
        temperature=temperature,
    )


def _make_gemini(temperature: float, purpose: str = "default") -> Any:
    from langchain_google_genai import ChatGoogleGenerativeAI

    cfg = get_settings()
    if not cfg.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set")
    logger.info("Factory → Gemini (%s) [purpose=%s]", cfg.GEMINI_MODEL, purpose)
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
    Configured with automatic fallbacks so 429 rate limits seamlessly fall back to secondary models.
    """
    cfg = get_settings()
    provider = (cfg.LLM_PROVIDER or "ollama").strip().lower()
    if provider not in _BUILDERS:
        logger.warning("Unknown LLM_PROVIDER=%r — falling back to ollama", provider)
        provider = "ollama"

    fallbacks: list[Any] = []

    if provider == "groq" and cfg.GROQ_API_KEY:
        # Fallback 1: Alternative Groq model (separate daily token quota)
        try:
            alt_model = (
                cfg.GROQ_RESEARCH_MODEL
                if purpose not in ("research", "coder")
                else cfg.GROQ_CHAT_MODEL
            )
            if alt_model and alt_model != (cfg.GROQ_CHAT_MODEL if purpose not in ("research", "coder") else cfg.GROQ_RESEARCH_MODEL):
                from langchain_groq import ChatGroq
                fallbacks.append(
                    ChatGroq(
                        model=alt_model,
                        groq_api_key=cfg.GROQ_API_KEY,
                        temperature=temperature,
                    )
                )
        except Exception as e:
            logger.debug("Could not add Groq alt fallback: %s", e)

        # Fallback 2: Gemini if key available
        if cfg.GEMINI_API_KEY:
            try:
                fallbacks.append(_make_gemini(temperature, purpose=purpose))
            except Exception as e:
                logger.debug("Could not add Gemini fallback: %s", e)

        # Fallback 3: Local Ollama (unlimited local fallback)
        try:
            fallbacks.append(_make_ollama(temperature, purpose=purpose))
        except Exception as e:
            logger.debug("Could not add Ollama fallback: %s", e)

    try:
        primary = _BUILDERS[provider](temperature, purpose=purpose)
        if fallbacks:
            return primary.with_fallbacks(fallbacks)
        return primary
    except Exception as e:
        if provider == "ollama":
            raise
        logger.warning(
            "LLM_PROVIDER=%s failed (%s) — falling back to Ollama", provider, e
        )
        return _make_ollama(temperature, purpose=purpose)
