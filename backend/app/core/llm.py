"""Centralized LLM Factory to manage Ollama models across all agents."""
from langchain_ollama import ChatOllama
from app.core.config import get_settings

def get_llm(temperature: float = 0.7) -> ChatOllama:
    """
    Creates and returns a ChatOllama instance using the model specified in the global config.
    """
    cfg = get_settings()
    
    return ChatOllama(
        base_url=cfg.OLLAMA_BASE_URL,
        model=cfg.OLLAMA_MODEL,
        temperature=temperature,
    )
