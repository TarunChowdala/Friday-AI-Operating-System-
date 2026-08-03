from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from langchain_core.tools import tool
from app.core.logger import get_logger

logger = get_logger(__name__)

# Initialize the search wrapper once
_search = DuckDuckGoSearchAPIWrapper()

@tool
def web_search(query: str) -> str:
    """Searches the web using DuckDuckGo to answer questions about current events, facts, or general knowledge."""
    logger.info("Executing web search tool for query: %s", query)
    try:
        return _search.run(query)
    except Exception as e:
        logger.error("Web search failed: %s", e)
        return f"Error performing web search: {e}"

def perform_direct_search(query: str) -> str:
    """A direct python function to perform search without the LangChain tool wrapper."""
    logger.info("Executing direct web search for query: %s", query)
    try:
        return _search.run(query)
    except Exception as e:
        logger.error("Web search failed: %s", e)
        return f"Error performing web search: {e}"
