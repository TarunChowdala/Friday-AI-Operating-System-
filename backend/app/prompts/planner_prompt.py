"""Planner agent prompt."""

PLANNER_PROMPT = """Break the user goal into ordered steps.
Each step should name the tool or agent needed.
Return a short numbered plan — no fluff.
"""


def build_planner_prompt(goal: str) -> str:
    return f"{PLANNER_PROMPT}

Goal: {goal}"
