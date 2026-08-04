"""Routes tasks to the right agent using Ollama."""
from typing import Any, Dict

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
            "Given the user's task or phrase, decide which specialized agent is best suited to handle it.\n\n"
            "Strict Routing Rules:\n"
            "- planner: DEFAULT AGENT. Use for ALL casual conversation, greetings (e.g. 'hello', 'how are you', 'I love red', 'tell me a joke', 'what's up'), general advice, opinions, chatting, or planning.\n"
            "- executor: Use ONLY when the user gives a direct system command to open an app, open a URL, play YouTube, change volume, pause/play media, inspect/read screen ('what can you see on screen'), copy/paste clipboard, or run terminal commands.\n"
            "- researcher: Use ONLY when the user asks a real-time factual query requiring live web search (e.g. 'latest news on AI', 'current stock price of Google', 'who won yesterday's game'). DO NOT use for casual phrases.\n"
            "- coder: Use ONLY when writing, refactoring, explaining, or debugging programming code.\n"
            "- critic: Use ONLY for evaluating complex logic or code reviews.\n\n"
            "Task: {task}\n\n"
            "Respond with exactly ONE word (the agent name) from the list above. Do not add any punctuation, quotes, or explanation."

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
