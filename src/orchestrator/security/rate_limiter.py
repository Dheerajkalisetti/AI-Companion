"""OmniCompanion — Rate Limiter

Token bucket rate limiting for Gemini API calls, actions,
screenshots, and browser navigations.
"""

from __future__ import annotations

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TokenBucketRateLimiter:
    """Token bucket rate limiter.

    Allows burst capacity up to the bucket size,
    then throttles to the configured rate.
    """

    def __init__(
        self,
        rate_per_minute: int,
        burst_size: Optional[int] = None,
        name: str = "default",
    ) -> None:
        """Initialize the rate limiter.

        Args:
            rate_per_minute: Maximum operations per minute.
            burst_size: Max burst size (defaults to rate_per_minute).
            name: Name for logging.
        """
        self.rate_per_minute = rate_per_minute
        self.burst_size = burst_size or rate_per_minute
        self.name = name

        # Internal state
        self._tokens = float(self.burst_size)
        self._last_refill = time.monotonic()
        self._total_consumed = 0
        self._total_throttled = 0

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now

        # Add tokens for elapsed time
        new_tokens = elapsed * (self.rate_per_minute / 60.0)
        self._tokens = min(self._tokens + new_tokens, float(self.burst_size))

    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without blocking.

        Args:
            tokens: Number of tokens to acquire.

        Returns:
            True if tokens were acquired, False if rate limited.
        """
        self._refill()

        if self._tokens >= tokens:
            self._tokens -= tokens
            self._total_consumed += tokens
            return True
        else:
            self._total_throttled += 1
            logger.warning(
                f"Rate limited: {self.name} "
                f"(available={self._tokens:.1f}, requested={tokens})"
            )
            return False

    def wait_time(self, tokens: int = 1) -> float:
        """Calculate wait time until tokens are available.

        Args:
            tokens: Number of tokens needed.

        Returns:
            Seconds to wait (0.0 if tokens available now).
        """
        self._refill()

        if self._tokens >= tokens:
            return 0.0

        deficit = tokens - self._tokens
        return deficit / (self.rate_per_minute / 60.0)

    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire.
        """
        import asyncio

        wait = self.wait_time(tokens)
        if wait > 0:
            logger.info(f"Rate limiter {self.name}: waiting {wait:.2f}s")
            await asyncio.sleep(wait)

        self._refill()
        self._tokens -= tokens
        self._total_consumed += tokens

    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        self._refill()
        return {
            "name": self.name,
            "rate_per_minute": self.rate_per_minute,
            "burst_size": self.burst_size,
            "available_tokens": round(self._tokens, 2),
            "total_consumed": self._total_consumed,
            "total_throttled": self._total_throttled,
        }


class RateLimiterRegistry:
    """Central registry for all rate limiters.

    Provides named rate limiters for different operation types
    based on the safety_rules.yaml configuration.
    """

    def __init__(self, config: Optional[dict] = None) -> None:
        """Initialize with rate limit configuration.

        Args:
            config: Rate limit config from safety_rules.yaml.
                    Keys: gemini_calls_per_minute, actions_per_minute, etc.
        """
        config = config or {}

        self.limiters = {
            "gemini": TokenBucketRateLimiter(
                rate_per_minute=config.get("gemini_calls_per_minute", 30),
                name="gemini",
            ),
            "actions": TokenBucketRateLimiter(
                rate_per_minute=config.get("actions_per_minute", 60),
                name="actions",
            ),
            "screenshots": TokenBucketRateLimiter(
                rate_per_minute=config.get("screenshots_per_minute", 20),
                name="screenshots",
            ),
            "browser": TokenBucketRateLimiter(
                rate_per_minute=config.get("browser_navigations_per_minute", 15),
                name="browser",
            ),
        }

    def get(self, name: str) -> TokenBucketRateLimiter:
        """Get a rate limiter by name.

        Args:
            name: Limiter name.

        Returns:
            The rate limiter.

        Raises:
            KeyError: If limiter name not found.
        """
        if name not in self.limiters:
            raise KeyError(f"Unknown rate limiter: {name}")
        return self.limiters[name]

    def get_all_stats(self) -> dict:
        """Get stats for all rate limiters."""
        return {
            name: limiter.get_stats()
            for name, limiter in self.limiters.items()
        }
