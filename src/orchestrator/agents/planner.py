"""OmniCompanion — Executive Planner Agent

Decomposes user goals into ordered task plans using Gemini reasoning.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.orchestrator.gemini.client import GeminiClient

from src.orchestrator.gemini.prompts import EXECUTIVE_PLANNER_SYSTEM

logger = logging.getLogger(__name__)


class ExecutivePlannerAgent:
    """Agent 1: Receives user goal → produces ordered task plan.

    Input: Natural language goal string
    Output: JSON task plan {tasks: [{id, description, agent, tools, dependencies}]}
    """

    def __init__(self, gemini_client: GeminiClient) -> None:
        self.gemini = gemini_client
        self.name = "executive_planner"

    async def execute(
        self,
        goal: str,
        context: Optional[dict] = None,
        memory_context: Optional[list[dict]] = None,
    ) -> dict:
        """Decompose a user goal into an ordered task plan.

        Args:
            goal: Natural language goal from the user.
            context: Optional current context (screen state, etc.)
            memory_context: Optional relevant past tasks from memory.

        Returns:
            Task plan JSON with ordered steps.

        Raises:
            ValueError: If Gemini returns unparseable response.
        """
        # Build the prompt
        prompt_parts = [f"USER GOAL: {goal}"]

        if context:
            prompt_parts.append(f"\nCURRENT CONTEXT:\n{json.dumps(context, indent=2)}")

        if memory_context:
            prompt_parts.append(
                f"\nRELEVANT PAST TASKS:\n{json.dumps(memory_context, indent=2)}"
            )

        prompt = "\n".join(prompt_parts)

        try:
            # Call Gemini
            response = await self.gemini.generate_text(
                prompt=prompt,
                system_instruction=EXECUTIVE_PLANNER_SYSTEM,
                response_mime_type="application/json",
                max_output_tokens=4096,
                temperature=0.1,
            )
            plan = json.loads(response)
        except Exception as e:
            logger.error(f"Planner API call failed: {e}")
            raise ValueError(f"Planner API call failed: {e}")

        # Validate structure
        if "tasks" not in plan:
            raise ValueError("Planner response missing 'tasks' key")

        for task in plan["tasks"]:
            required_keys = {"id", "description", "agent"}
            if not required_keys.issubset(task.keys()):
                missing = required_keys - task.keys()
                raise ValueError(f"Task missing required keys: {missing}")

        logger.info(
            "Task plan generated",
            extra={
                "goal": goal[:100],
                "step_count": len(plan["tasks"]),
            },
        )

        return plan
