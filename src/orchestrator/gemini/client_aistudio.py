"""OmniCompanion — Gemini Client (Google AI Studio)

Uses the google.genai SDK (new official package).
Supports text, multimodal, multi-turn conversation,
structured JSON output, and automatic retry with backoff.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import time
from typing import Any, Optional, Union

from google import genai
from google.genai import types
from PIL import Image as PILImage

logger = logging.getLogger(__name__)


class RequestRateLimiter:
    """Strictly limits requests per minute (RPM)."""
    def __init__(self, max_rpm: int = 5):
        self.max_rpm = max_rpm
        self.requests = []
        self.lock = asyncio.Lock()

    async def wait_for_slot(self):
        async with self.lock:
            while True:
                now = time.time()
                # Clear requests older than 60s
                self.requests = [r for r in self.requests if now - r < 60]
                
                if len(self.requests) < self.max_rpm:
                    self.requests.append(now)
                    return
                
                # Wait for the oldest request to expire
                wait_time = 60 - (now - self.requests[0]) + 0.1
                logger.info(f"Rate Limiter: Waiting {wait_time:.1f}s for RPM slot...")
                await asyncio.sleep(wait_time)

class GeminiClient:
    """Gemini client using Google AI Studio (API key auth).

    Features:
    - Text and multimodal (image + text) generation
    - Multi-turn conversation with history
    - Structured JSON output
    - Automatic retry with exponential backoff for 429 errors
    - Request rate limiting (strictly 5 RPM)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: str = "gemini-3-flash-preview",
        max_output_tokens: int = 8192,
        temperature: float = 0.1,
    ) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY not set. Add it to your .env file."
            )

        self.model_id = model_id
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature

        # Initialize the new google.genai client
        self.client = genai.Client(api_key=self.api_key)
        
        # Hard limit for free tier: 5 RPM
        self.limiter = RequestRateLimiter(max_rpm=5)

        logger.info(f"GeminiClient initialized (model={self.model_id}, limit=5 RPM)")

    @staticmethod
    def prepare_screenshot(raw_bytes: bytes, max_dim: int = 1024) -> bytes:
        """Resize screenshot for Gemini input."""
        img = PILImage.open(io.BytesIO(raw_bytes))
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), PILImage.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()

    async def _call_with_retry(self, func, max_retries: int = 5):
        """Call a function with automatic retry on rate limit (429)."""
        for attempt in range(max_retries + 1):
            try:
                # Strictly enforce RPM limit BEFORE calling
                await self.limiter.wait_for_slot()
                
                # Run the synchronous genai SDK call in a threadpool so it doesn't block CPU loop
                return await asyncio.to_thread(func)
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "quota" in error_str.lower():
                    if attempt < max_retries:
                        wait = min((attempt + 1) * 15, 60)
                        logger.warning(
                            f"Rate limited (attempt {attempt + 1}/{max_retries}). "
                            f"Waiting {wait}s for quota to reset..."
                        )
                        await asyncio.sleep(wait)
                        continue
                logger.error(f"Gemini API Error: {error_str}")
                raise

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        response_mime_type: str = "application/json",
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Generate text response from a prompt."""
        config = types.GenerateContentConfig(
            max_output_tokens=max_output_tokens or self.max_output_tokens,
            temperature=temperature if temperature is not None else self.temperature,
            response_mime_type=response_mime_type,
            system_instruction=system_instruction,
        )

        def _call():
            return self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=config,
            )

        response = await self._call_with_retry(_call)
        text = response.text
        logger.info(f"Gemini text response: {len(text)} chars")
        return text

    async def generate_multimodal(
        self,
        image_bytes: bytes,
        text_prompt: str,
        system_instruction: Optional[str] = None,
        response_mime_type: str = "application/json",
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Generate response from image + text."""
        optimized = self.prepare_screenshot(image_bytes)
        img = PILImage.open(io.BytesIO(optimized))

        config = types.GenerateContentConfig(
            max_output_tokens=max_output_tokens or self.max_output_tokens,
            temperature=temperature if temperature is not None else self.temperature,
            response_mime_type=response_mime_type,
            system_instruction=system_instruction,
        )

        def _call():
            return self.client.models.generate_content(
                model=self.model_id,
                contents=[img, text_prompt],
                config=config,
            )

        response = await self._call_with_retry(_call)
        text = response.text
        logger.info(f"Gemini multimodal response: {len(text)} chars")
        return text

    async def generate_with_history(
        self,
        messages: list[dict],
        system_instruction: Optional[str] = None,
        screenshot: Optional[bytes] = None,
        response_mime_type: str = "application/json",
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Generate response using full conversation history.

        This is the primary method for the companion brain. It maintains
        the full conversation context so the AI can reason about what
        has happened and what to do next.

        Args:
            messages: List of {"role": "user"|"model", "text": "..."} dicts.
            system_instruction: System prompt for the model.
            screenshot: Optional current screenshot (PNG bytes).
            response_mime_type: Response format.
            max_output_tokens: Override default max tokens.
            temperature: Override default temperature.

        Returns:
            Generated text response.
        """
        config = types.GenerateContentConfig(
            max_output_tokens=max_output_tokens or self.max_output_tokens,
            temperature=temperature if temperature is not None else self.temperature,
            response_mime_type=response_mime_type,
            system_instruction=system_instruction,
        )

        # Build contents list from conversation history
        contents = []
        for msg in messages:
            role = msg["role"]
            text = msg.get("text", "")
            
            if role == "user":
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=text)],
                ))
            elif role == "model":
                contents.append(types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=text)],
                ))

        # If we have a screenshot, add it to the last user message
        if screenshot and contents:
            optimized = self.prepare_screenshot(screenshot)
            
            # Find last user content or create a new one
            if contents[-1].role == "user":
                contents[-1].parts.append(types.Part.from_bytes(data=optimized, mime_type="image/png"))
            else:
                contents.append(types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text="[Screenshot of current screen attached]"),
                        types.Part.from_bytes(data=optimized, mime_type="image/png"),
                    ],
                ))

        def _call():
            return self.client.models.generate_content(
                model=self.model_id,
                contents=contents,
                config=config,
            )

        response = await self._call_with_retry(_call)
        text = response.text
        logger.info(f"Gemini conversation response: {len(text)} chars (history: {len(messages)} turns)")
        return text

    def count_tokens(self, contents) -> int:
        """Count tokens in content."""
        if isinstance(contents, str):
            contents = [contents]
        result = self.client.models.count_tokens(
            model=self.model_id,
            contents=contents,
        )
        return result.total_tokens
