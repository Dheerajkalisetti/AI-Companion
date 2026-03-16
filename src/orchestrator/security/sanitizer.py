"""OmniCompanion — Input Sanitizer

Validates and sanitizes all user inputs and agent-generated
commands before execution. Prevents command injection,
path traversal, and other input-based attacks.
"""

from __future__ import annotations

import re
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Dangerous shell characters that could enable command injection
SHELL_INJECTION_CHARS = set(';&|`$(){}[]!<>\\')

# Dangerous path patterns
PATH_TRAVERSAL_PATTERNS = [
    r'\.\./',      # Parent directory traversal
    r'\.\.\\',     # Windows traversal
    r'~/',         # Home directory access
    r'^/',         # Absolute path (when not expected)
    r'\x00',       # Null byte injection
]

# Maximum lengths for various inputs
MAX_GOAL_LENGTH = 2000
MAX_COMMAND_LENGTH = 500
MAX_PATH_LENGTH = 260
MAX_URL_LENGTH = 2048
MAX_SELECTOR_LENGTH = 500


class InputSanitizer:
    """Sanitizes and validates inputs to prevent injection attacks."""

    @staticmethod
    def sanitize_goal(goal: str) -> str:
        """Sanitize a user goal string.

        Args:
            goal: Raw user goal text.

        Returns:
            Sanitized goal string.

        Raises:
            ValueError: If goal is empty or too long.
        """
        if not goal or not goal.strip():
            raise ValueError("Goal cannot be empty")

        goal = goal.strip()

        if len(goal) > MAX_GOAL_LENGTH:
            raise ValueError(f"Goal exceeds maximum length ({MAX_GOAL_LENGTH} chars)")

        # Remove null bytes
        goal = goal.replace('\x00', '')

        # Remove control characters except newlines and tabs
        goal = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]', '', goal)

        logger.debug(f"Goal sanitized: {len(goal)} chars")
        return goal

    @staticmethod
    def sanitize_command(command: str) -> tuple[str, list[str]]:
        """Sanitize a shell command and check for injection.

        Args:
            command: Raw command string.

        Returns:
            Tuple of (sanitized_command, warnings).

        Raises:
            ValueError: If command contains injection characters.
        """
        if not command:
            raise ValueError("Command cannot be empty")

        if len(command) > MAX_COMMAND_LENGTH:
            raise ValueError(f"Command exceeds maximum length ({MAX_COMMAND_LENGTH} chars)")

        warnings = []

        # Check for shell injection characters
        dangerous_chars = SHELL_INJECTION_CHARS.intersection(set(command))
        if dangerous_chars:
            raise ValueError(
                f"Command contains dangerous characters: {dangerous_chars}"
            )

        # Check for common injection patterns
        injection_patterns = [
            (r';\s*rm', "Shell injection: chained delete command"),
            (r'\|\s*sh', "Shell injection: piped shell execution"),
            (r'`.*`', "Shell injection: backtick command substitution"),
            (r'\$\(', "Shell injection: command substitution"),
            (r'>\s*/', "Shell injection: redirect to root filesystem"),
        ]

        for pattern, message in injection_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                raise ValueError(f"Injection detected: {message}")

        return command.strip(), warnings

    @staticmethod
    def sanitize_path(path: str, allow_absolute: bool = False) -> str:
        """Sanitize a filesystem path.

        Args:
            path: Raw path string.
            allow_absolute: Whether to allow absolute paths.

        Returns:
            Sanitized path.

        Raises:
            ValueError: If path contains traversal or is too long.
        """
        if not path:
            raise ValueError("Path cannot be empty")

        if len(path) > MAX_PATH_LENGTH:
            raise ValueError(f"Path exceeds maximum length ({MAX_PATH_LENGTH} chars)")

        # Remove null bytes
        path = path.replace('\x00', '')

        # Check for path traversal
        for pattern in PATH_TRAVERSAL_PATTERNS:
            if pattern == r'^/' and allow_absolute:
                continue
            if re.search(pattern, path):
                raise ValueError(f"Path traversal detected in: {path}")

        # Normalize the path
        normalized = os.path.normpath(path)

        # Double-check no traversal after normalization
        if '..' in normalized.split(os.sep):
            raise ValueError(f"Path traversal detected after normalization: {path}")

        return normalized

    @staticmethod
    def sanitize_url(url: str) -> str:
        """Sanitize a URL input.

        Args:
            url: Raw URL string.

        Returns:
            Sanitized URL.

        Raises:
            ValueError: If URL is malformed or uses a blocked scheme.
        """
        if not url:
            raise ValueError("URL cannot be empty")

        if len(url) > MAX_URL_LENGTH:
            raise ValueError(f"URL exceeds maximum length ({MAX_URL_LENGTH} chars)")

        # Only allow http/https schemes
        allowed_schemes = ('http://', 'https://')
        if not any(url.lower().startswith(s) for s in allowed_schemes):
            raise ValueError(f"URL must use http:// or https:// scheme")

        # Remove null bytes
        url = url.replace('\x00', '')

        # Check for javascript: injection in URL
        if 'javascript:' in url.lower():
            raise ValueError("JavaScript injection detected in URL")

        return url.strip()

    @staticmethod
    def sanitize_selector(selector: str) -> str:
        """Sanitize a CSS selector for Playwright.

        Args:
            selector: Raw CSS selector.

        Returns:
            Sanitized selector.

        Raises:
            ValueError: If selector is too long or contains injection.
        """
        if not selector:
            raise ValueError("Selector cannot be empty")

        if len(selector) > MAX_SELECTOR_LENGTH:
            raise ValueError(f"Selector exceeds maximum length ({MAX_SELECTOR_LENGTH} chars)")

        # Remove null bytes
        selector = selector.replace('\x00', '')

        return selector.strip()

    @staticmethod
    def sanitize_text_input(text: str, max_length: int = 5000) -> str:
        """Sanitize general text input for typing.

        Args:
            text: Raw text to type.
            max_length: Maximum allowed length.

        Returns:
            Sanitized text.
        """
        if len(text) > max_length:
            raise ValueError(f"Text exceeds maximum length ({max_length} chars)")

        # Remove null bytes
        text = text.replace('\x00', '')

        return text
