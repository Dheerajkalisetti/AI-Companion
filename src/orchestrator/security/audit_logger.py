"""OmniCompanion — Structured Audit Logger

Produces structured JSON audit logs for all agent actions,
safety decisions, and system events. Supports both local
and Cloud Logging output.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AuditEvent:
    """Represents a single audit log event."""

    def __init__(
        self,
        event_type: str,
        agent: str,
        action: str,
        status: str = "info",
        details: Optional[dict] = None,
        risk_level: Optional[str] = None,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> None:
        self.event_id = str(uuid.uuid4())
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.event_type = event_type
        self.agent = agent
        self.action = action
        self.status = status
        self.details = details or {}
        self.risk_level = risk_level
        self.session_id = session_id
        self.task_id = task_id

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        record = {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "agent": self.agent,
            "action": self.action,
            "status": self.status,
        }
        if self.details:
            record["details"] = self.details
        if self.risk_level:
            record["risk_level"] = self.risk_level
        if self.session_id:
            record["session_id"] = self.session_id
        if self.task_id:
            record["task_id"] = self.task_id
        return record

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class AuditLogger:
    """Structured audit logger with local and cloud backends.

    Event Types:
    - goal_submitted: User goal received
    - plan_created: Task plan generated
    - action_executed: Agent action performed
    - safety_check: Safety decision made
    - verification: Task step verification
    - error: Error occurred
    - security_event: Security-relevant event
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        enable_cloud: bool = False,
    ) -> None:
        """Initialize the audit logger.

        Args:
            session_id: Current session ID.
            enable_cloud: Whether to send logs to Cloud Logging.
        """
        self.session_id = session_id
        self.enable_cloud = enable_cloud
        self._cloud_client = None
        self._events: list[AuditEvent] = []

        if enable_cloud:
            self._init_cloud_logging()

    def _init_cloud_logging(self) -> None:
        """Initialize Google Cloud Logging client."""
        try:
            from google.cloud import logging as cloud_logging

            self._cloud_client = cloud_logging.Client()
            self._cloud_logger = self._cloud_client.logger(
                os.environ.get("CLOUD_LOGGING_LOG_NAME", "omnicompanion-audit")
            )
            logger.info("Cloud Logging initialized")
        except Exception as e:
            logger.warning(f"Cloud Logging unavailable: {e}")
            self.enable_cloud = False

    def log(
        self,
        event_type: str,
        agent: str,
        action: str,
        status: str = "info",
        details: Optional[dict] = None,
        risk_level: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> AuditEvent:
        """Log an audit event.

        Args:
            event_type: Type of event.
            agent: Agent that triggered the event.
            action: Description of the action.
            status: Event status (info, success, error, warning).
            details: Additional event details.
            risk_level: Risk level if applicable.
            task_id: Associated task ID.

        Returns:
            The created AuditEvent.
        """
        event = AuditEvent(
            event_type=event_type,
            agent=agent,
            action=action,
            status=status,
            details=details,
            risk_level=risk_level,
            session_id=self.session_id,
            task_id=task_id,
        )

        # Store locally
        self._events.append(event)

        # Log to standard logger
        log_level = {
            "info": logging.INFO,
            "success": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
        }.get(status, logging.INFO)

        logger.log(log_level, f"AUDIT | {event.to_json()}")

        # Send to Cloud Logging
        if self.enable_cloud and self._cloud_logger:
            try:
                self._cloud_logger.log_struct(
                    event.to_dict(),
                    severity=status.upper(),
                )
            except Exception as e:
                logger.warning(f"Cloud Logging write failed: {e}")

        return event

    def log_goal(self, goal: str, task_id: str) -> AuditEvent:
        """Log a goal submission."""
        return self.log(
            event_type="goal_submitted",
            agent="orchestrator",
            action=f"Goal received: {goal[:100]}",
            details={"goal": goal, "goal_length": len(goal)},
            task_id=task_id,
        )

    def log_plan(self, plan: dict, task_id: str) -> AuditEvent:
        """Log a plan creation."""
        return self.log(
            event_type="plan_created",
            agent="planner",
            action=f"Plan with {len(plan.get('tasks', []))} steps",
            details={"step_count": len(plan.get("tasks", []))},
            task_id=task_id,
        )

    def log_action(
        self,
        agent: str,
        action: str,
        success: bool,
        task_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> AuditEvent:
        """Log an agent action execution."""
        return self.log(
            event_type="action_executed",
            agent=agent,
            action=action,
            status="success" if success else "error",
            details=details,
            task_id=task_id,
        )

    def log_safety(
        self,
        action: dict,
        approved: bool,
        risk_level: str,
        reason: str,
    ) -> AuditEvent:
        """Log a safety decision."""
        return self.log(
            event_type="safety_check",
            agent="safety_monitor",
            action=f"{'Approved' if approved else 'Blocked'}: {reason[:80]}",
            status="info" if approved else "warning",
            details={"action": str(action)[:200], "reason": reason},
            risk_level=risk_level,
        )

    def log_error(
        self,
        agent: str,
        error: str,
        task_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> AuditEvent:
        """Log an error."""
        return self.log(
            event_type="error",
            agent=agent,
            action=f"Error: {error[:100]}",
            status="error",
            details={**(details or {}), "error": error},
            task_id=task_id,
        )

    def log_security_event(
        self,
        description: str,
        severity: str = "warning",
        details: Optional[dict] = None,
    ) -> AuditEvent:
        """Log a security-relevant event."""
        return self.log(
            event_type="security_event",
            agent="security",
            action=description,
            status=severity,
            details=details,
            risk_level="high",
        )

    def get_recent_events(self, count: int = 20) -> list[dict]:
        """Get recent audit events."""
        return [e.to_dict() for e in self._events[-count:]]

    def get_events_by_type(self, event_type: str) -> list[dict]:
        """Get all events of a specific type."""
        return [
            e.to_dict()
            for e in self._events
            if e.event_type == event_type
        ]

    def get_security_events(self) -> list[dict]:
        """Get all security-relevant events."""
        security_types = {"safety_check", "security_event", "error"}
        return [
            e.to_dict()
            for e in self._events
            if e.event_type in security_types
        ]

    def get_stats(self) -> dict:
        """Get audit log statistics."""
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for e in self._events:
            by_type[e.event_type] = by_type.get(e.event_type, 0) + 1
            by_status[e.status] = by_status.get(e.status, 0) + 1

        return {
            "total_events": len(self._events),
            "by_type": by_type,
            "by_status": by_status,
        }
