"""OmniCompanion — Real Screen Capture (macOS)

Uses macOS native `screencapture` command for real
screenshot capture. Falls back to PyAutoGUI if available.
"""

from __future__ import annotations

import io
import logging
import os
import subprocess
import tempfile
from typing import Optional

from PIL import Image as PILImage

logger = logging.getLogger(__name__)


def capture_screen_macos() -> Optional[bytes]:
    """Capture the full screen on macOS using screencapture.

    Returns:
        PNG bytes of the screenshot, or None on failure.
    """
    try:
        # Create temp file for screenshot
        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)

        # Capture using macOS native tool (silent, no shadow)
        result = subprocess.run(
            ["screencapture", "-x", "-C", path],
            capture_output=True,
            timeout=5,
        )

        if result.returncode != 0:
            logger.error(f"screencapture failed: {result.stderr.decode()}")
            return None

        # Read the screenshot
        with open(path, "rb") as f:
            screenshot_bytes = f.read()

        # Clean up
        os.unlink(path)

        logger.info(f"Screen captured: {len(screenshot_bytes)} bytes")
        return screenshot_bytes

    except FileNotFoundError:
        logger.error("screencapture not found (not macOS?)")
        return None
    except subprocess.TimeoutExpired:
        logger.error("screencapture timed out")
        return None
    except Exception as e:
        logger.error(f"Screen capture failed: {e}")
        return None


def capture_region_macos(x: int, y: int, w: int, h: int) -> Optional[bytes]:
    """Capture a rectangular region of the screen.

    Args:
        x, y: Top-left corner coordinates.
        w, h: Width and height of the region.

    Returns:
        PNG bytes of the cropped region, or None on failure.
    """
    full = capture_screen_macos()
    if not full:
        return None

    try:
        img = PILImage.open(io.BytesIO(full))
        cropped = img.crop((x, y, x + w, y + h))
        buffer = io.BytesIO()
        cropped.save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception as e:
        logger.error(f"Region capture failed: {e}")
        return None


def get_screen_size() -> tuple[int, int]:
    """Get the primary display resolution.

    Returns:
        (width, height) tuple.
    """
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Parse resolution from output
        for line in result.stdout.split("\n"):
            if "Resolution" in line:
                parts = line.split(":")[-1].strip()
                # Format: "2560 x 1600 Retina" or similar
                dims = parts.split("x")
                if len(dims) >= 2:
                    w = int(dims[0].strip().split()[0])
                    h = int(dims[1].strip().split()[0])
                    return (w, h)
    except Exception as e:
        logger.warning(f"Could not get screen size: {e}")

    return (1920, 1080)  # Fallback
