"""Routes tasks to the right agent using Ollama."""
from typing import Any, Dict

from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.core.config import get_settings
from app.core.logger import get_logger
from app.core.llm import get_llm

from app.agents.coder import CoderAgent
from app.agents.critic import CriticAgent
from app.agents.executor import ExecutorAgent
from app.agents.planner import PlannerAgent
from app.agents.researcher import ResearcherAgent

logger = get_logger(__name__)

class AgentRouter:
    def __init__(self) -> None:
        cfg = get_settings()
        
        # Initialize our local Ollama model for fast, smart routing
        self.llm = get_llm(temperature=0.0)
        
        self.agents = {
            "planner": PlannerAgent(),
            "researcher": ResearcherAgent(),
            "coder": CoderAgent(),
            "executor": ExecutorAgent(),
            "critic": CriticAgent(),
        }
        
        # Setup the LangChain routing pipeline
        prompt = PromptTemplate.from_template(
            "You are the central routing brain for a personal AI assistant named FRIDAY.\n"
            "Given the user's task, decide which specialized agent is best suited to handle it.\n\n"
            "Available Agents:\n"
            "- planner: For general questions, casual chatting, or creating step-by-step plans.\n"
            "- researcher: For web searches, finding facts, or reading documentation.\n"
            "- coder: For writing, refactoring, explaining, or fixing code.\n"
            "- executor: For running terminal commands, scripts, or modifying local system files.\n"
            "- critic: For reviewing code or evaluating complex logic.\n\n"
            "Task: {task}\n\n"
            "Respond with exactly ONE word (the agent name) from the list above. Do not add punctuation or explanation."
        )
        self.router_chain = prompt | self.llm | StrOutputParser()

    async def route(self, task: str) -> str:
        """Uses Ollama to smartly determine which agent should handle the task."""
        try:
            decision = await self.router_chain.ainvoke({"task": task})
            decision = decision.strip().lower()
            
            logger.info("Ollama routed task to: %s", decision)
            
            # Ensure the LLM didn't hallucinate a fake agent name
            if decision in self.agents:
                return decision
                
            logger.warning("Ollama returned invalid agent '%s', falling back to planner", decision)
            return "planner"
            
        except Exception as e:
            logger.error("Ollama routing failed: %s", e)
            return "planner" # Fallback if LLM is offline

    async def dispatch(self, agent_name: str, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Sends the task to the chosen agent."""
        agent = self.agents.get(agent_name) or self.agents["planner"]
        return await agent.run(task, context)

    async def stream_dispatch(self, agent_name: str, task: str, context: Dict[str, Any]):
        """Streams the task to the chosen agent."""
        agent = self.agents.get(agent_name) or self.agents["planner"]
        
        # Fallback to normal run if stream isn't implemented (for other agents)
        if not hasattr(agent, "stream"):
            result = await agent.run(task, context)
            yield result.get("result", "")
            return
            
        async for chunk in agent.stream(task, context):
            yield chunk
