"""OmniCompanion — Short-Term Memory

In-memory session store for the current task context,
conversation history, and screen state.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ShortTermMemory:
    """Fast in-memory session storage.

    Stores conversation history, task history, screen history,
    active plan, and token budget for the current session.
    """

    def __init__(self, max_screen_history: int = 10, max_task_history: int = 100) -> None:
        self.session_id = str(uuid.uuid4())
        self.max_screen_history = max_screen_history
        self.max_task_history = max_task_history

        self._store: dict[str, Any] = {
            "session_id": self.session_id,
            "conversation_history": [],
            "task_history": [],
            "screen_history": [],
            "active_plan": None,
            "token_budget": {
                "used": 0,
                "limit": 1_000_000,
                "last_reset": datetime.now(timezone.utc).isoformat(),
            },
        }

        logger.info(f"ShortTermMemory initialized: session={self.session_id}")

    # ──────────────────────────────────────
    # Conversation History
    # ──────────────────────────────────────

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history.

        Args:
            role: "user" or "model" (matches Gemini's role naming).
            content: The message text.
        """
        self._store["conversation_history"].append({
            "role": role,
            "text": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Keep conversation history manageable (last 50 turns)
        if len(self._store["conversation_history"]) > 50:
            self._store["conversation_history"] = self._store["conversation_history"][-50:]

    def get_conversation_history(self, max_turns: int = 20) -> list[dict]:
        """Get recent conversation history for the Gemini API.

        Returns list of {"role": "user"|"model", "text": "..."} dicts.
        """
        return self._store["conversation_history"][-max_turns:]

    def get_conversation_for_display(self, max_turns: int = 20) -> list[dict]:
        """Get conversation history with timestamps for UI display."""
        return self._store["conversation_history"][-max_turns:]

    # ──────────────────────────────────────
    # Task History
    # ──────────────────────────────────────

    def add_task(self, goal: str) -> str:
        """Add a new task to history.

        Args:
            goal: The user's goal text.

        Returns:
            Generated task ID.
        """
        task_id = str(uuid.uuid4())
        task = {
            "task_id": task_id,
            "goal": goal,
            "status": "pending",
            "steps": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._store["task_history"].append(task)

        # Prune if over limit
        if len(self._store["task_history"]) > self.max_task_history:
            self._store["task_history"] = self._store["task_history"][-self.max_task_history:]

        return task_id

    def update_task_status(self, task_id: str, status: str) -> None:
        """Update a task's status.

        Args:
            task_id: The task identifier.
            status: New status (pending|in_progress|completed|failed).
        """
        for task in self._store["task_history"]:
            if task["task_id"] == task_id:
                task["status"] = status
                return

    def add_step(self, task_id: str, agent: str, action: str, result: Any) -> str:
        """Add an execution step to a task.

        Args:
            task_id: The parent task ID.
            agent: Agent that executed the step.
            action: Description of the action.
            result: Step result data.

        Returns:
            Generated step ID.
        """
        step_id = str(uuid.uuid4())
        step = {
            "step_id": step_id,
            "agent": agent,
            "action": action,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        for task in self._store["task_history"]:
            if task["task_id"] == task_id:
                task["steps"].append(step)
                break

        return step_id

    # ──────────────────────────────────────
    # Screen History
    # ──────────────────────────────────────

    def add_screen(self, screenshot_ref: str, ui_elements: list, context: str = "") -> None:
        """Add a screen capture to history.

        Args:
            screenshot_ref: Reference to screenshot (GCS path or in-memory key).
            ui_elements: List of detected UI elements.
            context: Optional context description.
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "screenshot_ref": screenshot_ref,
            "ui_elements": ui_elements,
            "context": context,
        }
        self._store["screen_history"].append(entry)

        # Prune oldest
        if len(self._store["screen_history"]) > self.max_screen_history:
            self._store["screen_history"] = self._store["screen_history"][-self.max_screen_history:]

    # ──────────────────────────────────────
    # Plan & Budget
    # ──────────────────────────────────────

    def set_active_plan(self, plan: dict) -> None:
        """Set the currently active task plan."""
        self._store["active_plan"] = plan

    def get_active_plan(self) -> Optional[dict]:
        """Get the currently active task plan."""
        return self._store["active_plan"]

    def get_recent_tasks(self, count: int = 5) -> list[dict]:
        """Get most recent tasks."""
        return self._store["task_history"][-count:]

    def get_recent_screens(self, count: int = 3) -> list[dict]:
        """Get most recent screen captures."""
        return self._store["screen_history"][-count:]

    def update_token_budget(self, tokens_used: int) -> None:
        """Update the token budget counter."""
        self._store["token_budget"]["used"] += tokens_used

    def get_token_budget(self) -> dict:
        """Get current token budget state."""
        return self._store["token_budget"]

    def get(self, key: str) -> Any:
        """Get a value by key from the store."""
        return self._store.get(key)

    def set(self, key: str, value: Any) -> None:
        """Set a value by key in the store."""
        self._store[key] = value

    def clear(self) -> None:
        """Clear all session data."""
        self._store["conversation_history"] = []
        self._store["task_history"] = []
        self._store["screen_history"] = []
        self._store["active_plan"] = None
        self._store["token_budget"]["used"] = 0
        logger.info(f"ShortTermMemory cleared: session={self.session_id}")
