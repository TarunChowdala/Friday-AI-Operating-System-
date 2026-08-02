"""Routes tasks across specialized agents."""
from typing import Any, Dict

from app.agents.router import AgentRouter
from app.core.logger import get_logger

logger = get_logger(__name__)


class AgentManager:
    def __init__(self) -> None:
        self.router = AgentRouter()

    async def run(self, task: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        context = context or {}
        agent_name = await self.router.route(task)
        logger.info("routing task → %s", agent_name)
        return await self.router.dispatch(agent_name, task, context)
