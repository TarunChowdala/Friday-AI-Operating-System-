"""Routes tasks to the right agent."""
from typing import Any, Dict

from app.agents.coder import CoderAgent
from app.agents.critic import CriticAgent
from app.agents.executor import ExecutorAgent
from app.agents.planner import PlannerAgent
from app.agents.researcher import ResearcherAgent


class AgentRouter:
    def __init__(self) -> None:
        self.agents = {
            "planner": PlannerAgent(),
            "researcher": ResearcherAgent(),
            "coder": CoderAgent(),
            "executor": ExecutorAgent(),
            "critic": CriticAgent(),
        }

    async def route(self, task: str) -> str:
        lowered = task.lower()
        if any(k in lowered for k in ("code", "fix", "implement", "refactor")):
            return "coder"
        if any(k in lowered for k in ("search", "research", "find", "lookup")):
            return "researcher"
        if any(k in lowered for k in ("run", "execute", "do", "open")):
            return "executor"
        if any(k in lowered for k in ("review", "check", "critique")):
            return "critic"
        return "planner"

    async def dispatch(self, agent_name: str, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        agent = self.agents.get(agent_name) or self.agents["planner"]
        return await agent.run(task, context)
