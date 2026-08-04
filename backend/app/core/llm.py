"""Centralized LLM Factory to manage Ollama models across all agents."""
from typing import Any
from app.llms.factory import get_llm as factory_get_llm

def get_llm(temperature: float = 0.7, purpose: str = "default") -> Any:
    """
    Creates and returns an LLM instance using the model specified in the global config.
    Delegates to the new purpose-based factory.
    """
    return factory_get_llm(purpose=purpose, temperature=temperature)
