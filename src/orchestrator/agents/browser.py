"""OmniCompanion — Browser Automation Agent

Web-specific automation via Playwright.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

logger = logging.getLogger(__name__)


class BrowserAutomationAgent:
    """Agent 4: Browser automation via Playwright.

    Input: {action, selector, url, value}
    Output: {url, title, screenshot, dom_snapshot}
    """

    def __init__(
        self,
        browser_type: str = "chromium",
        headless: bool = False,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
    ) -> None:
        self.name = "browser_automation"
        self.browser_type = browser_type
        self.headless = headless
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def launch(self) -> None:
        """Launch the browser."""
        self._playwright = await async_playwright().start()

        launcher = getattr(self._playwright, self.browser_type)
        self._browser = await launcher.launch(headless=self.headless)
        self._context = await self._browser.new_context(
            viewport={"width": self.viewport_width, "height": self.viewport_height}
        )
        self._page = await self._context.new_page()

        logger.info(
            f"Browser launched: {self.browser_type}, headless={self.headless}"
        )

    async def close(self) -> None:
        """Close the browser."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser closed")

    async def execute(self, action: dict) -> dict:
        """Execute a browser action.

        Args:
            action: Browser action command JSON.

        Returns:
            Browser state after action.
        """
        if not self._page:
            await self.launch()

        action_type = action.get("action", "")

        try:
            if action_type == "navigate":
                return await self._navigate(action)
            elif action_type == "click":
                return await self._click(action)
            elif action_type == "type":
                return await self._type(action)
            elif action_type == "screenshot":
                return await self._screenshot()
            elif action_type == "dom_snapshot":
                return await self._dom_snapshot()
            elif action_type == "wait":
                return await self._wait(action)
            elif action_type == "scroll":
                return await self._scroll(action)
            else:
                return {
                    "url": self._page.url if self._page else "",
                    "title": "",
                    "screenshot": None,
                    "dom_snapshot": None,
                    "error": f"Unknown action: {action_type}",
                }
        except Exception as e:
            logger.error(f"Browser action failed: {e}")
            return {
                "url": self._page.url if self._page else "",
                "title": "",
                "screenshot": None,
                "dom_snapshot": None,
                "error": str(e),
            }

    async def _navigate(self, action: dict) -> dict:
        """Navigate to URL."""
        url = action.get("url", "")
        await self._page.goto(url, wait_until="domcontentloaded")

        screenshot = await self._page.screenshot(type="png")
        return {
            "url": self._page.url,
            "title": await self._page.title(),
            "screenshot": screenshot,
            "dom_snapshot": None,
        }

    async def _click(self, action: dict) -> dict:
        """Click element by selector."""
        selector = action.get("selector", "")
        await self._page.click(selector, timeout=action.get("timeout_ms", 30000))

        screenshot = await self._page.screenshot(type="png")
        return {
            "url": self._page.url,
            "title": await self._page.title(),
            "screenshot": screenshot,
            "dom_snapshot": None,
        }

    async def _type(self, action: dict) -> dict:
        """Type text into element."""
        selector = action.get("selector", "")
        value = action.get("value", "")
        await self._page.fill(selector, value)

        screenshot = await self._page.screenshot(type="png")
        return {
            "url": self._page.url,
            "title": await self._page.title(),
            "screenshot": screenshot,
            "dom_snapshot": None,
        }

    async def _screenshot(self) -> dict:
        """Take a screenshot."""
        screenshot = await self._page.screenshot(type="png")
        return {
            "url": self._page.url,
            "title": await self._page.title(),
            "screenshot": screenshot,
            "dom_snapshot": None,
        }

    async def _dom_snapshot(self) -> dict:
        """Extract DOM snapshot."""
        content = await self._page.content()
        return {
            "url": self._page.url,
            "title": await self._page.title(),
            "screenshot": None,
            "dom_snapshot": content,
        }

    async def _wait(self, action: dict) -> dict:
        """Wait for specified time or selector."""
        if "selector" in action:
            await self._page.wait_for_selector(
                action["selector"], timeout=action.get("timeout_ms", 30000)
            )
        else:
            await self._page.wait_for_timeout(action.get("wait_ms", 1000))

        return {
            "url": self._page.url,
            "title": await self._page.title(),
            "screenshot": None,
            "dom_snapshot": None,
        }

    async def _scroll(self, action: dict) -> dict:
        """Scroll the page."""
        delta_y = action.get("delta_y", 300)
        await self._page.evaluate(f"window.scrollBy(0, {delta_y})")

        screenshot = await self._page.screenshot(type="png")
        return {
            "url": self._page.url,
            "title": await self._page.title(),
            "screenshot": screenshot,
            "dom_snapshot": None,
        }
