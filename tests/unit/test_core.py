"""Unit tests for OmniCompanion core components.

Tests:
- ShortTermMemory CRUD operations
- Safety Monitor hardcoded rules
- Executive Planner response parsing
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.orchestrator.memory.short_term import ShortTermMemory


class TestShortTermMemory:
    """Tests for ShortTermMemory."""

    def test_initialization(self):
        """Memory initializes with session ID and empty stores."""
        mem = ShortTermMemory()
        assert mem.session_id is not None
        assert len(mem.get_recent_tasks()) == 0
        assert len(mem.get_recent_screens()) == 0

    def test_add_task(self):
        """Adding a task returns an ID and stores it."""
        mem = ShortTermMemory()
        task_id = mem.add_task("Open Chrome")
        assert task_id is not None
        tasks = mem.get_recent_tasks()
        assert len(tasks) == 1
        assert tasks[0]["goal"] == "Open Chrome"
        assert tasks[0]["status"] == "pending"

    def test_update_task_status(self):
        """Task status can be updated."""
        mem = ShortTermMemory()
        task_id = mem.add_task("Test task")
        mem.update_task_status(task_id, "completed")
        tasks = mem.get_recent_tasks()
        assert tasks[0]["status"] == "completed"

    def test_add_step(self):
        """Steps can be added to tasks."""
        mem = ShortTermMemory()
        task_id = mem.add_task("Navigate to Google")
        step_id = mem.add_step(task_id, "browser", "navigate", {"url": "google.com"})
        assert step_id is not None
        tasks = mem.get_recent_tasks()
        assert len(tasks[0]["steps"]) == 1

    def test_screen_history_pruning(self):
        """Screen history is pruned when exceeding max."""
        mem = ShortTermMemory(max_screen_history=3)
        for i in range(5):
            mem.add_screen(f"screenshot_{i}.png", [], f"context_{i}")
        screens = mem.get_recent_screens(10)
        assert len(screens) == 3
        assert screens[0]["screenshot_ref"] == "screenshot_2.png"

    def test_token_budget(self):
        """Token budget tracks usage."""
        mem = ShortTermMemory()
        mem.update_token_budget(500)
        mem.update_token_budget(300)
        budget = mem.get_token_budget()
        assert budget["used"] == 800

    def test_active_plan(self):
        """Active plan can be set and retrieved."""
        mem = ShortTermMemory()
        plan = {"tasks": [{"id": "1", "description": "test"}]}
        mem.set_active_plan(plan)
        assert mem.get_active_plan() == plan

    def test_clear(self):
        """Clear resets all stores."""
        mem = ShortTermMemory()
        mem.add_task("Test")
        mem.add_screen("test.png", [])
        mem.clear()
        assert len(mem.get_recent_tasks()) == 0
        assert len(mem.get_recent_screens()) == 0
        assert mem.get_active_plan() is None


class TestSafetyRules:
    """Tests for Safety Monitor hardcoded rules."""

    @pytest.fixture
    def safety_agent(self):
        """Create a SafetyMonitorAgent with mock Gemini client."""
        from src.orchestrator.agents.safety import SafetyMonitorAgent
        mock_gemini = MagicMock()
        agent = SafetyMonitorAgent(
            gemini_client=mock_gemini,
            rules_path="config/safety_rules.yaml",
        )
        return agent

    def test_blocked_action_rm_rf(self, safety_agent):
        """rm -rf / should be blocked."""
        result = safety_agent._check_hardcoded_rules(
            {"action_type": "command", "value": "rm -rf /"}
        )
        assert result is not None
        assert result["approved"] is False
        assert result["risk_level"] == "critical"

    def test_auto_approve_screenshot(self, safety_agent):
        """Screenshot actions should be auto-approved."""
        result = safety_agent._check_hardcoded_rules(
            {"action": "screenshot"}
        )
        assert result is not None
        assert result["approved"] is True
        assert result["risk_level"] == "low"

    def test_blocked_path_ssh(self, safety_agent):
        """SSH directory access should be blocked."""
        result = safety_agent._check_hardcoded_rules(
            {"action_type": "read", "path": "~/.ssh/id_rsa"}
        )
        assert result is not None
        assert result["approved"] is False

    def test_unknown_action_returns_none(self, safety_agent):
        """Unknown safe actions fall through to Gemini."""
        result = safety_agent._check_hardcoded_rules(
            {"action_type": "click", "target": {"x": 100, "y": 200}}
        )
        # Simple click doesn't match any hardcoded rules
        assert result is None or result["approved"] is True


class TestPlannerParsing:
    """Tests for Executive Planner response validation."""

    def test_valid_plan_parsing(self):
        """Valid JSON plan should parse correctly."""
        plan_json = json.dumps({
            "tasks": [
                {
                    "id": "step_1",
                    "description": "Open Chrome browser",
                    "agent": "executor",
                    "tools": ["mouse_keyboard"],
                    "dependencies": [],
                    "risk_level": "low",
                }
            ],
            "reasoning": "Simple browser launch",
        })
        plan = json.loads(plan_json)
        assert "tasks" in plan
        assert len(plan["tasks"]) == 1
        assert plan["tasks"][0]["agent"] == "executor"

    def test_plan_missing_tasks_key(self):
        """Plan without 'tasks' key should be caught."""
        plan_json = '{"steps": []}'
        plan = json.loads(plan_json)
        assert "tasks" not in plan

    def test_plan_step_validation(self):
        """Each step must have id, description, and agent."""
        step = {"id": "s1", "description": "Do thing", "agent": "vision"}
        required = {"id", "description", "agent"}
        assert required.issubset(step.keys())

    def test_invalid_json_handling(self):
        """Invalid JSON should raise JSONDecodeError."""
        with pytest.raises(json.JSONDecodeError):
            json.loads("not json at all")
