"""Unit tests for Phase 9 security modules.

Tests:
- InputSanitizer (injection prevention, path traversal)
- TokenBucketRateLimiter (rate limiting, burst)
- AuditLogger (structured logging)
- Error types and retry utilities
"""

import pytest
import time
from unittest.mock import AsyncMock

from src.orchestrator.security.sanitizer import InputSanitizer
from src.orchestrator.security.rate_limiter import (
    TokenBucketRateLimiter,
    RateLimiterRegistry,
)
from src.orchestrator.security.audit_logger import AuditLogger, AuditEvent
from src.orchestrator.security.errors import (
    OmniCompanionError,
    GeminiAPIError,
    SafetyBlockedError,
    ActionExecutionError,
    InputValidationError,
    retry_async,
    format_error,
)


# ──────────────────────────────────────
# Input Sanitizer Tests
# ──────────────────────────────────────

class TestInputSanitizer:
    """Tests for InputSanitizer."""

    def test_sanitize_goal_normal(self):
        """Normal goal should pass through."""
        result = InputSanitizer.sanitize_goal("Open Chrome and go to Google")
        assert result == "Open Chrome and go to Google"

    def test_sanitize_goal_strips_whitespace(self):
        """Goal should be trimmed."""
        result = InputSanitizer.sanitize_goal("  Open Chrome  ")
        assert result == "Open Chrome"

    def test_sanitize_goal_empty(self):
        """Empty goal should raise."""
        with pytest.raises(ValueError, match="empty"):
            InputSanitizer.sanitize_goal("")

    def test_sanitize_goal_too_long(self):
        """Overly long goal should raise."""
        with pytest.raises(ValueError, match="maximum length"):
            InputSanitizer.sanitize_goal("x" * 3000)

    def test_sanitize_goal_removes_null_bytes(self):
        """Null bytes should be stripped."""
        result = InputSanitizer.sanitize_goal("Open\x00Chrome")
        assert "\x00" not in result

    def test_sanitize_goal_removes_control_chars(self):
        """Control characters should be stripped."""
        result = InputSanitizer.sanitize_goal("Open\x01\x02Chrome")
        assert result == "OpenChrome"

    def test_sanitize_command_injection(self):
        """Shell injection should be blocked."""
        with pytest.raises(ValueError, match="dangerous characters"):
            InputSanitizer.sanitize_command("echo hello; rm -rf /")

    def test_sanitize_command_backtick_injection(self):
        """Backtick injection should be blocked."""
        with pytest.raises(ValueError, match="dangerous characters"):
            InputSanitizer.sanitize_command("echo `whoami`")

    def test_sanitize_command_pipe_injection(self):
        """Pipe injection should be blocked."""
        with pytest.raises(ValueError, match="dangerous characters"):
            InputSanitizer.sanitize_command("cat file | sh")

    def test_sanitize_path_traversal(self):
        """Path traversal should be blocked."""
        with pytest.raises(ValueError, match="traversal"):
            InputSanitizer.sanitize_path("../../etc/passwd")

    def test_sanitize_path_normal(self):
        """Normal relative path should pass."""
        result = InputSanitizer.sanitize_path("documents/file.txt")
        assert "file.txt" in result

    def test_sanitize_path_absolute_blocked(self):
        """Absolute path should be blocked by default."""
        with pytest.raises(ValueError, match="traversal"):
            InputSanitizer.sanitize_path("/etc/passwd")

    def test_sanitize_path_absolute_allowed(self):
        """Absolute path can be allowed explicitly."""
        result = InputSanitizer.sanitize_path("/home/user/file.txt", allow_absolute=True)
        assert "file.txt" in result

    def test_sanitize_url_valid(self):
        """Valid HTTPS URL should pass."""
        result = InputSanitizer.sanitize_url("https://google.com")
        assert result == "https://google.com"

    def test_sanitize_url_http(self):
        """HTTP URL should pass."""
        result = InputSanitizer.sanitize_url("http://example.com")
        assert result == "http://example.com"

    def test_sanitize_url_blocked_scheme(self):
        """Non-http schemes should be blocked."""
        with pytest.raises(ValueError, match="scheme"):
            InputSanitizer.sanitize_url("ftp://evil.com")

    def test_sanitize_url_javascript_injection(self):
        """javascript: URLs should be blocked."""
        with pytest.raises(ValueError, match="JavaScript injection"):
            InputSanitizer.sanitize_url("https://example.com/javascript:alert(1)")

    def test_sanitize_selector(self):
        """Normal selector should pass."""
        result = InputSanitizer.sanitize_selector("#submit-btn")
        assert result == "#submit-btn"


# ──────────────────────────────────────
# Rate Limiter Tests
# ──────────────────────────────────────

class TestRateLimiter:
    """Tests for TokenBucketRateLimiter."""

    def test_initial_tokens_available(self):
        """Should have initial burst capacity."""
        rl = TokenBucketRateLimiter(rate_per_minute=60, name="test")
        assert rl.try_acquire(1) is True

    def test_burst_capacity(self):
        """Should allow burst up to burst_size."""
        rl = TokenBucketRateLimiter(rate_per_minute=60, burst_size=5, name="test")
        for _ in range(5):
            assert rl.try_acquire(1) is True
        # Next should be rate limited
        assert rl.try_acquire(1) is False

    def test_stats(self):
        """Stats should reflect usage."""
        rl = TokenBucketRateLimiter(rate_per_minute=60, burst_size=10, name="test")
        rl.try_acquire(3)
        rl.try_acquire(2)
        stats = rl.get_stats()
        assert stats["name"] == "test"
        assert stats["total_consumed"] == 5
        assert stats["rate_per_minute"] == 60

    def test_wait_time_when_empty(self):
        """Wait time should be positive when tokens depleted."""
        rl = TokenBucketRateLimiter(rate_per_minute=60, burst_size=1, name="test")
        rl.try_acquire(1)
        wait = rl.wait_time(1)
        assert wait > 0

    def test_wait_time_when_available(self):
        """Wait time should be 0 when tokens available."""
        rl = TokenBucketRateLimiter(rate_per_minute=60, name="test")
        wait = rl.wait_time(1)
        assert wait == 0.0


class TestRateLimiterRegistry:
    """Tests for RateLimiterRegistry."""

    def test_default_limiters_exist(self):
        """Registry should have all default limiters."""
        registry = RateLimiterRegistry()
        for name in ["gemini", "actions", "screenshots", "browser"]:
            limiter = registry.get(name)
            assert limiter is not None

    def test_unknown_limiter_raises(self):
        """Unknown limiter name should raise KeyError."""
        registry = RateLimiterRegistry()
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_custom_config(self):
        """Custom config should override defaults."""
        registry = RateLimiterRegistry({"gemini_calls_per_minute": 10})
        stats = registry.get("gemini").get_stats()
        assert stats["rate_per_minute"] == 10

    def test_all_stats(self):
        """Should return stats for all limiters."""
        registry = RateLimiterRegistry()
        all_stats = registry.get_all_stats()
        assert len(all_stats) == 4


# ──────────────────────────────────────
# Audit Logger Tests
# ──────────────────────────────────────

class TestAuditLogger:
    """Tests for AuditLogger."""

    def test_log_event(self):
        """Should create and store an event."""
        logger = AuditLogger(session_id="test-session")
        event = logger.log("test_event", "test_agent", "test action")
        assert event.event_type == "test_event"
        assert event.agent == "test_agent"
        assert event.session_id == "test-session"

    def test_log_goal(self):
        """Should log goal submission."""
        audit = AuditLogger()
        event = audit.log_goal("Open Chrome", "task-123")
        assert event.event_type == "goal_submitted"
        assert "Chrome" in event.action

    def test_log_safety(self):
        """Should log safety decisions."""
        audit = AuditLogger()
        event = audit.log_safety(
            action={"type": "click"},
            approved=True,
            risk_level="low",
            reason="Auto-approved",
        )
        assert event.event_type == "safety_check"
        assert event.risk_level == "low"

    def test_get_recent_events(self):
        """Should return recent events."""
        audit = AuditLogger()
        for i in range(5):
            audit.log("test", "agent", f"action {i}")
        events = audit.get_recent_events(3)
        assert len(events) == 3

    def test_get_stats(self):
        """Should provide stats summary."""
        audit = AuditLogger()
        audit.log("goal_submitted", "orchestrator", "goal 1")
        audit.log("action_executed", "executor", "action 1")
        audit.log("error", "verifier", "error 1", status="error")
        stats = audit.get_stats()
        assert stats["total_events"] == 3
        assert stats["by_type"]["goal_submitted"] == 1
        assert stats["by_status"]["error"] == 1


class TestAuditEvent:
    """Tests for AuditEvent."""

    def test_to_dict(self):
        """Should produce valid dict."""
        event = AuditEvent("test", "agent", "action")
        d = event.to_dict()
        assert "event_id" in d
        assert "timestamp" in d
        assert d["event_type"] == "test"

    def test_to_json(self):
        """Should produce valid JSON string."""
        event = AuditEvent("test", "agent", "action")
        j = event.to_json()
        import json
        parsed = json.loads(j)
        assert parsed["event_type"] == "test"


# ──────────────────────────────────────
# Error Types Tests
# ──────────────────────────────────────

class TestErrorTypes:
    """Tests for structured error types."""

    def test_base_error(self):
        """Base error should have agent and recoverable fields."""
        err = OmniCompanionError("test", agent="test_agent", recoverable=False)
        assert str(err) == "test"
        assert err.agent == "test_agent"
        assert err.recoverable is False

    def test_gemini_error(self):
        """GeminiAPIError should include status code."""
        err = GeminiAPIError("rate limited", status_code=429)
        assert err.status_code == 429
        assert err.recoverable is True

    def test_safety_blocked_error(self):
        """SafetyBlockedError should not be recoverable."""
        err = SafetyBlockedError("dangerous action", risk_level="critical")
        assert err.recoverable is False
        assert err.risk_level == "critical"

    def test_format_error(self):
        """format_error should produce structured dict."""
        err = GeminiAPIError("rate limited", status_code=429)
        formatted = format_error(err)
        assert formatted["error_type"] == "GeminiAPIError"
        assert formatted["status_code"] == 429
        assert formatted["recoverable"] is True


class TestRetryAsync:
    """Tests for retry_async utility."""

    @pytest.mark.asyncio
    async def test_succeeds_first_try(self):
        """Should return result on first success."""
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await retry_async(func, max_retries=3)
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure(self):
        """Should retry on exception and succeed."""
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return "ok"

        result = await retry_async(
            func,
            max_retries=3,
            backoff_base=0.01,
        )
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        """Should raise after exhausting retries."""
        async def func():
            raise ValueError("always fail")

        with pytest.raises(ValueError, match="always fail"):
            await retry_async(func, max_retries=2, backoff_base=0.01)
