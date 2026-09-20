import os
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper, GoogleSerperAPIWrapper
from langchain_core.tools import tool
from app.core.logger import get_logger
from app.core.config import get_settings

logger = get_logger(__name__)

cfg = get_settings()

_ddg_search = DuckDuckGoSearchAPIWrapper()
_serper_search = None

if cfg.SERPER_API_KEY:
    os.environ["SERPER_API_KEY"] = cfg.SERPER_API_KEY
    try:
        _serper_search = GoogleSerperAPIWrapper()
        logger.info("Serper API configured for search.")
    except Exception as e:
        logger.warning("Failed to initialize Serper search: %s", e)

def _execute_search(query: str) -> str:
    if _serper_search:
        try:
            logger.info("Executing Google Serper search for query: %s", query)
            return _serper_search.run(query)
        except Exception as e:
            logger.warning("Serper search failed (%s), falling back to DuckDuckGo", e)
    
    logger.info("Executing DuckDuckGo search for query: %s", query)
    try:
        return _ddg_search.run(query)
    except Exception as e:
        logger.error("All search methods failed: %s", e)
        return f"Error performing web search: {e}"

@tool
def web_search(query: str) -> str:
    """Searches the web to answer questions about current events, facts, or general knowledge."""
    return _execute_search(query)

def perform_direct_search(query: str) -> str:
    """A direct python function to perform search without the LangChain tool wrapper."""
    return _execute_search(query)
