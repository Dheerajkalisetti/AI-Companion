"""E2E test scenarios for OmniCompanion.

Tests complete user-facing workflows from goal submission
through execution and verification, with fully mocked backends.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.fixtures.mock_responses import (
    MOCK_PLANNER_RESPONSE,
    MOCK_VISION_RESPONSE,
    MOCK_VERIFICATION_SUCCESS,
    MOCK_SAFETY_APPROVED,
    MOCK_SCREENSHOT_BYTES,
    build_mock_plan_response,
)
from src.orchestrator.memory.short_term import ShortTermMemory


class TestE2EScenarios:
    """End-to-end test scenarios simulating real user workflows."""

    @pytest.mark.asyncio
    async def test_e2e_open_browser_goal(self):
        """E2E: User says 'Open Chrome' → system plans, executes, verifies."""
        from src.orchestrator.agents.planner import ExecutivePlannerAgent
        from src.orchestrator.agents.vision import UIVisionAgent
        from src.orchestrator.agents.executor import ActionExecutorAgent
        from src.orchestrator.agents.verifier import VerificationAgent
        from src.orchestrator.agents.safety import SafetyMonitorAgent
        from src.orchestrator.agents.memory import MemoryAgent

        # Mock Gemini
        mock_gemini = MagicMock()
        mock_gemini.generate_text = AsyncMock()
        mock_gemini.generate_multimodal = AsyncMock()

        # Step 1: Plan
        mock_gemini.generate_text.return_value = MOCK_PLANNER_RESPONSE
        planner = ExecutivePlannerAgent(mock_gemini)
        plan = await planner.execute("Open Chrome browser")
        assert len(plan["tasks"]) == 4

        # Step 2: Vision analysis
        mock_gemini.generate_multimodal.return_value = MOCK_VISION_RESPONSE
        vision = UIVisionAgent(mock_gemini)
        ui_map = await vision.execute(MOCK_SCREENSHOT_BYTES, context="Find Chrome")
        chrome_icon = next(
            (e for e in ui_map["elements"] if "Chrome" in e["label"]),
            None,
        )
        assert chrome_icon is not None
        assert chrome_icon["confidence"] >= 0.9

        # Step 3: Execute click
        executor = ActionExecutorAgent()
        click_result = await executor.execute({
            "action_type": "click",
            "target": {
                "x": chrome_icon["bbox"][0] + chrome_icon["bbox"][2] // 2,
                "y": chrome_icon["bbox"][1] + chrome_icon["bbox"][3] // 2,
            },
        })
        assert click_result["success"] is True

        # Step 4: Verify
        mock_gemini.generate_multimodal.return_value = MOCK_VERIFICATION_SUCCESS
        verifier = VerificationAgent(mock_gemini)
        verification = await verifier.execute(
            "Chrome browser should now be open",
            MOCK_SCREENSHOT_BYTES,
        )
        assert verification["verified"] is True
        assert verification["confidence"] >= 0.85

    @pytest.mark.asyncio
    async def test_e2e_safety_blocks_dangerous_goal(self):
        """E2E: Dangerous goals should be blocked before planning."""
        from src.orchestrator.agents.safety import SafetyMonitorAgent

        mock_gemini = MagicMock()
        safety = SafetyMonitorAgent(
            gemini_client=mock_gemini,
            rules_path="config/safety_rules.yaml",
        )

        # User tries to delete system files
        result = await safety.execute({
            "action_type": "command",
            "value": "rm -rf /",
        })

        assert result["approved"] is False
        assert result["risk_level"] == "critical"
        # Goal should never reach the planner

    @pytest.mark.asyncio
    async def test_e2e_memory_persists_across_tasks(self):
        """E2E: Information stored in task 1 is available in task 2."""
        from src.orchestrator.agents.memory import MemoryAgent

        stm = ShortTermMemory()
        memory = MemoryAgent(stm)

        # Task 1: Store a learned pattern
        await memory.execute({
            "op": "write",
            "key": "chrome_dock_position",
            "data": {"x": 800, "y": 1050, "app": "Chrome"},
        })

        # Task 2: Retrieve the pattern
        result = await memory.execute({
            "op": "read",
            "key": "chrome_dock_position",
        })

        assert result["found"] is True
        assert result["data"]["app"] == "Chrome"
        assert result["data"]["x"] == 800

    @pytest.mark.asyncio
    async def test_e2e_verification_failure_triggers_retry(self):
        """E2E: When verification fails, the step should be retried."""
        from src.orchestrator.agents.verifier import VerificationAgent

        mock_gemini = MagicMock()

        # First attempt fails, second succeeds
        mock_gemini.generate_multimodal = AsyncMock(side_effect=[
            json.dumps({
                "verified": False,
                "confidence": 0.3,
                "evidence": "Chrome not found",
                "issues": ["Click missed target"],
                "suggestions": "Try different coordinates",
            }),
            MOCK_VERIFICATION_SUCCESS,
        ])

        verifier = VerificationAgent(mock_gemini)

        # First verification fails
        result1 = await verifier.execute("Chrome open", MOCK_SCREENSHOT_BYTES)
        assert result1["verified"] is False

        # Retry succeeds
        result2 = await verifier.execute("Chrome open", MOCK_SCREENSHOT_BYTES)
        assert result2["verified"] is True

    @pytest.mark.asyncio
    async def test_e2e_multi_step_goal(self):
        """E2E: Complex goal with multiple dependent steps."""
        from src.orchestrator.agents.planner import ExecutivePlannerAgent

        mock_gemini = MagicMock()

        # Complex 6-step plan
        complex_plan = json.dumps({
            "tasks": [
                {"id": "s1", "description": "Capture screen", "agent": "vision",
                 "tools": ["screen_capture"], "dependencies": [], "risk_level": "low"},
                {"id": "s2", "description": "Find browser", "agent": "vision",
                 "tools": ["gemini_multimodal"], "dependencies": ["s1"], "risk_level": "low"},
                {"id": "s3", "description": "Open browser", "agent": "executor",
                 "tools": ["mouse_keyboard"], "dependencies": ["s2"], "risk_level": "low"},
                {"id": "s4", "description": "Wait for browser", "agent": "executor",
                 "tools": [], "dependencies": ["s3"], "risk_level": "low"},
                {"id": "s5", "description": "Navigate to google.com", "agent": "browser",
                 "tools": ["playwright"], "dependencies": ["s4"], "risk_level": "low"},
                {"id": "s6", "description": "Verify Google loaded", "agent": "verifier",
                 "tools": ["screen_capture", "gemini_multimodal"], "dependencies": ["s5"],
                 "risk_level": "low"},
            ],
            "reasoning": "Open browser, navigate to Google, verify.",
        })

        mock_gemini.generate_text = AsyncMock(return_value=complex_plan)

        planner = ExecutivePlannerAgent(mock_gemini)
        plan = await planner.execute("Open Chrome and go to google.com")

        assert len(plan["tasks"]) == 6
        # Verify dependency chain
        assert plan["tasks"][2]["dependencies"] == ["s2"]
        assert plan["tasks"][5]["dependencies"] == ["s5"]

    @pytest.mark.asyncio
    async def test_e2e_task_tracking(self):
        """E2E: Task history is properly tracked in short-term memory."""
        stm = ShortTermMemory()

        # Create task
        task_id = stm.add_task("Navigate to Google")
        assert stm.get_recent_tasks(1)[0]["status"] == "pending"

        # Mark in progress
        stm.update_task_status(task_id, "in_progress")
        assert stm.get_recent_tasks(1)[0]["status"] == "in_progress"

        # Add steps
        stm.add_step(task_id, "planner", "Plan created", {"steps": 4})
        stm.add_step(task_id, "vision", "Screen analyzed", {"elements": 12})
        stm.add_step(task_id, "executor", "Chrome opened", {"success": True})
        stm.add_step(task_id, "verifier", "Verified", {"confidence": 0.95})

        # Complete
        stm.update_task_status(task_id, "completed")

        task = stm.get_recent_tasks(1)[0]
        assert task["status"] == "completed"
        assert len(task["steps"]) == 4

    @pytest.mark.asyncio
    async def test_e2e_token_budget_tracking(self):
        """E2E: Token usage is tracked across operations."""
        stm = ShortTermMemory()

        budget = stm.get_token_budget()
        assert budget["used"] == 0

        # Simulate token usage across agents
        stm.update_token_budget(1500)   # Planner
        stm.update_token_budget(3000)   # Vision (multimodal)
        stm.update_token_budget(500)    # Safety
        stm.update_token_budget(2000)   # Verifier

        budget = stm.get_token_budget()
        assert budget["used"] == 7000
        assert budget["used"] < budget["limit"]
