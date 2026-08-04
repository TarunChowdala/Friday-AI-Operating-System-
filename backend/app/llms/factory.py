from typing import Any
from langchain_ollama import ChatOllama
from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)

def get_llm(purpose: str = "default", temperature: float = 0.7) -> Any:
    """
    Centralized LLM Factory.
    Routes to the correct model based on the purpose/task.
    Available purposes:
    - default: Standard fast chatting (Ollama)
    - complex_reasoning: Deep reasoning and coding (Gemini if available, fallback to Ollama)
    - summarization: Fast API model for summarizing context
    """
    cfg = get_settings()
    
    # 1. Complex Reasoning
    if purpose == "complex_reasoning" and cfg.GEMINI_API_KEY:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            logger.info("Factory routing 'complex_reasoning' to Gemini Pro")
            return ChatGoogleGenerativeAI(
                model="gemini-pro",
                google_api_key=cfg.GEMINI_API_KEY,
                temperature=temperature
            )
        except ImportError:
            logger.warning("langchain-google-genai not installed. Falling back to local model.")
            
    # 2. Summarization
    if purpose == "summarization" and cfg.GEMINI_API_KEY:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            logger.info("Factory routing 'summarization' to Gemini Pro")
            return ChatGoogleGenerativeAI(
                model="gemini-pro",
                google_api_key=cfg.GEMINI_API_KEY,
                temperature=temperature
            )
        except ImportError:
            logger.warning("langchain-google-genai not installed. Falling back to local model.")

    # 1. Groq Integration (Ultra-fast 800+ tokens/sec cloud LLM)
    if True:
        try:
            from langchain_groq import ChatGroq
            logger.info(f"Factory routing '{purpose}' to Groq Cloud ({cfg.GROQ_MODEL})")
            return ChatGroq(
                model=cfg.GROQ_MODEL,
                groq_api_key=cfg.GROQ_API_KEY,
                temperature=temperature
            )
        except ImportError:
            logger.warning("langchain-groq not installed. Falling back to next provider.")

    # 2. Gemini Integration
    if False:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            logger.info(f"Factory routing '{purpose}' to Gemini Pro")
            return ChatGoogleGenerativeAI(
                model="gemini-pro",
                google_api_key=cfg.GEMINI_API_KEY,
                temperature=temperature
            )
        except ImportError:
            logger.warning("langchain-google-genai not installed. Falling back to local Ollama.")

    # 3. Fallback: Local Ollama
    logger.info(f"Factory routing '{purpose}' to Local Ollama ({cfg.OLLAMA_MODEL})")
    return ChatOllama(
        base_url=cfg.OLLAMA_BASE_URL,
        model=cfg.OLLAMA_MODEL,
        temperature=temperature,
    )
