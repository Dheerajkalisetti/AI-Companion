"""OmniCompanion — Safety Monitor Agent

Risk classification for proposed actions. Combines hardcoded
rules with Gemini-based risk assessment.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from src.orchestrator.gemini.client import GeminiClient

from src.orchestrator.gemini.prompts import SAFETY_MONITOR_SYSTEM

logger = logging.getLogger(__name__)


class SafetyMonitorAgent:
    """Agent 7: Classifies risk of proposed actions.

    Input: Proposed action JSON
    Output: {approved: bool, risk_level, reason}
    """

    def __init__(
        self,
        gemini_client: GeminiClient,
        rules_path: Optional[str] = None,
    ) -> None:
        self.gemini = gemini_client
        self.name = "safety_monitor"

        # Load safety rules
        rules_path = rules_path or os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "config", "safety_rules.yaml"
        )
        self.rules = self._load_rules(rules_path)

    def _load_rules(self, path: str) -> dict:
        """Load safety rules from YAML file."""
        try:
            with open(path, "r") as f:
                rules = yaml.safe_load(f)
            logger.info(f"Safety rules loaded from {path}")
            return rules or {}
        except (FileNotFoundError, yaml.YAMLError) as e:
            logger.warning(f"Could not load safety rules: {e}. Using defaults.")
            return {
                "blocked_actions": [],
                "confirmation_required": [],
                "blocked_paths": [],
                "auto_approve": [],
            }

    def _check_hardcoded_rules(self, action: dict) -> Optional[dict]:
        """Check action against hardcoded safety rules (fast path).

        Args:
            action: Proposed action JSON.

        Returns:
            Safety decision if rule matches, None otherwise.
        """
        action_str = json.dumps(action).lower()

        # Check blocked actions (never allowed)
        for rule in self.rules.get("blocked_actions", []):
            if rule.get("pattern", "").lower() in action_str:
                return {
                    "approved": False,
                    "risk_level": "critical",
                    "reason": rule.get("reason", "Action blocked by safety rule"),
                    "requires_confirmation": False,
                    "warnings": [f"Blocked pattern: {rule['pattern']}"],
                }

        # Check blocked paths
        for rule in self.rules.get("blocked_paths", []):
            path = rule.get("path", "")
            if path and path.lower() in action_str:
                return {
                    "approved": False,
                    "risk_level": "critical",
                    "reason": rule.get("reason", f"Path '{path}' is protected"),
                    "requires_confirmation": False,
                    "warnings": [f"Protected path: {path}"],
                }

        # Check auto-approve (fast path)
        action_type = action.get("action_type", action.get("action", "")).lower()
        for rule in self.rules.get("auto_approve", []):
            if rule.get("action", "").lower() == action_type:
                return {
                    "approved": True,
                    "risk_level": rule.get("risk", "low"),
                    "reason": f"Auto-approved: {action_type} is a safe operation",
                    "requires_confirmation": False,
                    "warnings": [],
                }

        # Check confirmation-required actions
        for rule in self.rules.get("confirmation_required", []):
            if rule.get("pattern", "").lower() in action_str:
                risk = rule.get("risk", "high")
                return {
                    "approved": risk in ("low", "medium"),
                    "risk_level": risk,
                    "reason": rule.get("reason", "Action requires confirmation"),
                    "requires_confirmation": risk in ("high", "critical"),
                    "warnings": [f"Matched pattern: {rule['pattern']}"],
                }

        return None

    async def execute(self, action: dict) -> dict:
        """Classify risk of a proposed action.

        First checks hardcoded rules (fast path), then falls back
        to Gemini for complex risk assessment.

        Args:
            action: Proposed action JSON.

        Returns:
            Safety decision: {approved, risk_level, reason, requires_confirmation, warnings}
        """
        # Fast path: hardcoded rules
        rule_result = self._check_hardcoded_rules(action)
        if rule_result is not None:
            logger.info(
                "Safety check (rules)",
                extra={
                    "action": str(action)[:100],
                    "approved": rule_result["approved"],
                    "risk_level": rule_result["risk_level"],
                },
            )
            return rule_result

        # Slow path: Gemini assessment
        prompt = f"Assess the risk of this proposed action:\n{json.dumps(action, indent=2)}"

        try:
            response = await self.gemini.generate_text(
                prompt=prompt,
                system_instruction=SAFETY_MONITOR_SYSTEM,
                response_mime_type="application/json",
                max_output_tokens=1024,
                temperature=0.0,
            )

            result = json.loads(response)
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Gemini safety assessment failed: {e}")
            result = {
                "approved": False,
                "risk_level": "unknown",
                "reason": f"Safety assessment failed: {e}",
                "requires_confirmation": True,
                "warnings": ["Gemini safety check failed"],
            }

        # Ensure required fields
        result.setdefault("approved", False)
        result.setdefault("risk_level", "medium")
        result.setdefault("reason", "")
        result.setdefault("requires_confirmation", result["risk_level"] in ("high", "critical"))
        result.setdefault("warnings", [])

        # Override: critical actions are never auto-approved
        if result["risk_level"] == "critical":
            result["approved"] = False
            result["requires_confirmation"] = True

        logger.info(
            "Safety check (Gemini)",
            extra={
                "action": str(action)[:100],
                "approved": result["approved"],
                "risk_level": result["risk_level"],
            },
        )

        return result
