"""OmniCompanion — Mock Fixtures for Testing

Provides mock Gemini responses, fake screenshots, and test data
for offline testing without real API calls.
"""

import json
from typing import Any


# ──────────────────────────────────────
# Mock Gemini Responses
# ──────────────────────────────────────

MOCK_PLANNER_RESPONSE = json.dumps({
    "tasks": [
        {
            "id": "step_1",
            "description": "Capture screenshot of current desktop",
            "agent": "vision",
            "tools": ["screen_capture"],
            "dependencies": [],
            "risk_level": "low",
        },
        {
            "id": "step_2",
            "description": "Identify the Chrome browser icon on the dock",
            "agent": "vision",
            "tools": ["gemini_multimodal"],
            "dependencies": ["step_1"],
            "risk_level": "low",
        },
        {
            "id": "step_3",
            "description": "Click the Chrome browser icon",
            "agent": "executor",
            "tools": ["mouse_keyboard"],
            "dependencies": ["step_2"],
            "risk_level": "low",
        },
        {
            "id": "step_4",
            "description": "Verify Chrome has opened",
            "agent": "verifier",
            "tools": ["screen_capture", "gemini_multimodal"],
            "dependencies": ["step_3"],
            "risk_level": "low",
        },
    ],
    "reasoning": "Opening Chrome requires locating it visually, clicking it, and verifying it launched.",
})

MOCK_VISION_RESPONSE = json.dumps({
    "elements": [
        {
            "type": "icon",
            "label": "Google Chrome",
            "bbox": [800, 1050, 48, 48],
            "confidence": 0.95,
            "clickable": True,
            "state": "enabled",
        },
        {
            "type": "icon",
            "label": "Finder",
            "bbox": [650, 1050, 48, 48],
            "confidence": 0.92,
            "clickable": True,
            "state": "enabled",
        },
        {
            "type": "icon",
            "label": "Terminal",
            "bbox": [900, 1050, 48, 48],
            "confidence": 0.89,
            "clickable": True,
            "state": "enabled",
        },
    ],
    "screen_description": "macOS desktop with dock visible at bottom",
    "active_window": "Desktop",
})

MOCK_VERIFICATION_SUCCESS = json.dumps({
    "verified": True,
    "confidence": 0.94,
    "evidence": "Chrome browser window is now visible with the new tab page open",
    "issues": [],
    "suggestions": "",
})

MOCK_VERIFICATION_FAILURE = json.dumps({
    "verified": False,
    "confidence": 0.35,
    "evidence": "Desktop still shows no Chrome window",
    "issues": ["Chrome did not open — possible wrong click target"],
    "suggestions": "Re-capture screenshot and try clicking at different coordinates",
})

MOCK_SAFETY_APPROVED = json.dumps({
    "approved": True,
    "risk_level": "low",
    "reason": "Clicking an application icon is a safe, read-only operation",
    "requires_confirmation": False,
    "warnings": [],
})

MOCK_SAFETY_BLOCKED = json.dumps({
    "approved": False,
    "risk_level": "critical",
    "reason": "Attempting to delete system files",
    "requires_confirmation": False,
    "warnings": ["Destructive file operation detected"],
})


# ──────────────────────────────────────
# Mock Screenshot (1x1 pixel PNG)
# ──────────────────────────────────────

# Minimal valid 1x1 PNG (69 bytes, generated with Pillow)
MOCK_SCREENSHOT_BYTES = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
    b'\x00\x00\x0cIDATx\x9cchhh\x00\x00\x03\x04'
    b'\x01\x81K\xd3\xd2\x10\x00\x00\x00\x00IEND\xaeB`\x82'
)


# ──────────────────────────────────────
# Helper builders
# ──────────────────────────────────────

def build_mock_task(goal: str = "Open Chrome", steps: int = 3) -> dict:
    """Build a mock task for testing."""
    return {
        "task_id": "test-task-001",
        "goal": goal,
        "status": "pending",
        "steps": [
            {
                "step_id": f"step_{i}",
                "agent": "executor",
                "action": f"Action {i}",
                "result": {"success": True},
                "timestamp": "2026-03-05T02:00:00Z",
            }
            for i in range(steps)
        ],
    }


def build_mock_action(
    action_type: str = "click",
    x: int = 500,
    y: int = 300,
    value: str = "",
) -> dict:
    """Build a mock action for safety testing."""
    action = {
        "action_type": action_type,
        "target": {"x": x, "y": y, "description": "Test target"},
    }
    if value:
        action["value"] = value
    return action


def build_mock_plan_response(steps: int = 4) -> str:
    """Build a mock planner response with N steps."""
    tasks = []
    agents = ["vision", "executor", "browser", "verifier"]
    for i in range(steps):
        tasks.append({
            "id": f"step_{i+1}",
            "description": f"Test step {i+1}",
            "agent": agents[i % len(agents)],
            "tools": ["test_tool"],
            "dependencies": [f"step_{i}"] if i > 0 else [],
            "risk_level": "low",
        })

    return json.dumps({"tasks": tasks, "reasoning": "Mock plan"})
