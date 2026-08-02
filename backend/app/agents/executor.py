"""Executor agent — runs planned tool actions."""
from typing import Any, Dict

from app.core.logger import get_logger

logger = get_logger(__name__)


class ExecutorAgent:
    name = "executor"

    async def run(self, task: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        context = context or {}
        logger.debug("executor agent: %s", task[:80])
        # TODO: implement executor agent
        return {"agent": self.name, "task": task, "result": "stub", "context_keys": list(context.keys())}
