"""OmniCompanion — Error Handling Utilities

Structured error types, retry helpers, and graceful degradation
utilities for production resilience.
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from typing import Any, Callable, Optional, TypeVar
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ──────────────────────────────────────
# Error Types
# ──────────────────────────────────────

class OmniCompanionError(Exception):
    """Base error for all OmniCompanion exceptions."""

    def __init__(self, message: str, agent: str = "", recoverable: bool = True) -> None:
        super().__init__(message)
        self.agent = agent
        self.recoverable = recoverable


class GeminiAPIError(OmniCompanionError):
    """Error communicating with Gemini API."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message, agent="gemini_client", recoverable=True)
        self.status_code = status_code


class SafetyBlockedError(OmniCompanionError):
    """Action was blocked by the safety monitor."""

    def __init__(self, message: str, risk_level: str = "high") -> None:
        super().__init__(message, agent="safety_monitor", recoverable=False)
        self.risk_level = risk_level


class ActionExecutionError(OmniCompanionError):
    """Error executing an OS-level action."""

    def __init__(self, message: str, action_type: str = "") -> None:
        super().__init__(message, agent="action_executor", recoverable=True)
        self.action_type = action_type


class VerificationError(OmniCompanionError):
    """Task verification failed."""

    def __init__(self, message: str, confidence: float = 0.0) -> None:
        super().__init__(message, agent="verifier", recoverable=True)
        self.confidence = confidence


class MemoryError(OmniCompanionError):
    """Error accessing memory storage."""

    def __init__(self, message: str) -> None:
        super().__init__(message, agent="memory", recoverable=True)


class InputValidationError(OmniCompanionError):
    """Input failed validation/sanitization."""

    def __init__(self, message: str) -> None:
        super().__init__(message, agent="sanitizer", recoverable=False)


# ──────────────────────────────────────
# Retry Helpers
# ──────────────────────────────────────

async def retry_async(
    func: Callable,
    max_retries: int = 3,
    backoff_base: float = 1.0,
    backoff_max: float = 30.0,
    retryable_exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None,
) -> Any:
    """Retry an async function with exponential backoff.

    Args:
        func: Async callable to retry.
        max_retries: Maximum retry attempts.
        backoff_base: Base delay multiplier.
        backoff_max: Maximum delay seconds.
        retryable_exceptions: Exception types to retry on.
        on_retry: Callback called on each retry (attempt, exception).

    Returns:
        Result of the function call.

    Raises:
        The last exception if all retries fail.
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except retryable_exceptions as e:
            last_exception = e

            if attempt == max_retries:
                break

            delay = min(backoff_base * (2 ** attempt), backoff_max)

            if on_retry:
                on_retry(attempt + 1, e)

            logger.warning(
                f"Retry {attempt + 1}/{max_retries}: {type(e).__name__}: {e} "
                f"(waiting {delay:.1f}s)"
            )
            await asyncio.sleep(delay)

    raise last_exception


def safe_execute(default: Any = None):
    """Decorator for graceful degradation.

    Returns default value instead of raising on error.
    Logs the error for debugging.

    Args:
        default: Value to return on error.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(
                    f"safe_execute caught error in {func.__name__}: "
                    f"{type(e).__name__}: {e}"
                )
                return default
        return wrapper
    return decorator


# ──────────────────────────────────────
# Error Formatting
# ──────────────────────────────────────

def format_error(error: Exception, include_traceback: bool = False) -> dict:
    """Format an exception into a structured dict.

    Args:
        error: The exception.
        include_traceback: Whether to include full traceback.

    Returns:
        Structured error dict.
    """
    result = {
        "error_type": type(error).__name__,
        "message": str(error),
        "recoverable": getattr(error, "recoverable", True),
        "agent": getattr(error, "agent", "unknown"),
    }

    if include_traceback:
        result["traceback"] = traceback.format_exc()

    # Add type-specific fields
    if isinstance(error, GeminiAPIError):
        result["status_code"] = error.status_code
    elif isinstance(error, SafetyBlockedError):
        result["risk_level"] = error.risk_level
    elif isinstance(error, VerificationError):
        result["confidence"] = error.confidence

    return result
