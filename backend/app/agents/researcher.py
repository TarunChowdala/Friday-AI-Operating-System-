from typing import Any, Dict
from langchain_core.prompts import PromptTemplate
from app.core.logger import get_logger
from app.core.llm import get_llm
from app.tools.search import perform_direct_search

logger = get_logger(__name__)

class ResearcherAgent:
    name = "researcher"

    def __init__(self) -> None:
        self.llm = get_llm(temperature=0.3)
        
        self.prompt = PromptTemplate.from_template(
            "You are FRIDAY, a highly intelligent personal AI assistant.\n"
            "You must refer to the user as 'Boss'.\n"
            "Answer the user's question using the provided Web Search Results.\n"
            "Keep your response concise, conversational, and direct.\n\n"
            "Search Results:\n{search_results}\n\n"
            "Boss: {task}\n"
            "FRIDAY:"
        )
        self.chain = self.prompt | self.llm

    async def run(self, task: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        context = context or {}
        logger.info("ResearcherAgent received task: %s", task[:80])
        
        try:
            results = perform_direct_search(task)
            response = await self.chain.ainvoke({"task": task, "search_results": results})
            ai_text = response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            logger.error("ResearcherAgent failed: %s", e)
            ai_text = "I'm sorry Boss, my web search module encountered an error."

        return {
            "agent": self.name,
            "task": task,
            "result": ai_text,
            "context_keys": list(context.keys())
        }

    async def stream(self, task: str, context: Dict[str, Any] | None = None):
        """Streams the LLM response chunk by chunk."""
        logger.info("ResearcherAgent streaming task: %s", task[:80])
        try:
            # Yield a filler phrase instantly so the UI reacts and she speaks immediately
            yield "Let me search the web for that, Boss. "
            
            # Perform the search in the background
            results = perform_direct_search(task)
            
            # Stream the final answer
            async for chunk in self.chain.astream({"task": task, "search_results": results}):
                yield chunk.content if hasattr(chunk, 'content') else str(chunk)
        except Exception as e:
            logger.error("ResearcherAgent stream failed: %s", e)
            yield "I encountered an error while searching the web."
