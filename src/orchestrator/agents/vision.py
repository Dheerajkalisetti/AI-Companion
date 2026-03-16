"""OmniCompanion — UI Vision Agent

Analyzes screenshots to identify UI elements using Gemini multimodal.
"""

from __future__ import annotations

import json
import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.orchestrator.gemini.client import GeminiClient

from src.orchestrator.gemini.prompts import UI_VISION_SYSTEM

logger = logging.getLogger(__name__)


class UIVisionAgent:
    """Agent 2: Screenshot analysis and UI element detection.

    Input: PNG screenshot bytes + optional context
    Output: {elements: [{type, label, bbox, confidence}]}
    """

    def __init__(self, gemini_client: GeminiClient) -> None:
        self.gemini = gemini_client
        self.name = "ui_vision"

    async def execute(
        self,
        screenshot_bytes: bytes,
        context: Optional[str] = None,
        ocr_text: Optional[str] = None,
    ) -> dict:
        """Analyze a screenshot and identify UI elements.

        Args:
            screenshot_bytes: PNG screenshot bytes.
            context: Optional task context.
            ocr_text: Optional OCR-extracted text.

        Returns:
            UI element map with bounding boxes.
        """
        prompt_parts = ["Analyze this screenshot and identify all interactive UI elements."]

        if context:
            prompt_parts.append(f"\nTASK CONTEXT: {context}")

        if ocr_text:
            prompt_parts.append(f"\nOCR TEXT DETECTED:\n{ocr_text}")

        prompt = "\n".join(prompt_parts)

        try:
            response = await self.gemini.generate_multimodal(
                image_bytes=screenshot_bytes,
                text_prompt=prompt,
                system_instruction=UI_VISION_SYSTEM,
                response_mime_type="application/json",
                max_output_tokens=4096,
            )
            result = json.loads(response)
        except Exception as e:
            logger.error(f"Vision API call failed: {e}")
            # Return honest error — no fake data
            result = {
                "elements": [],
                "screen_description": f"Vision analysis unavailable: {e}",
                "active_window": "unknown",
                "error": str(e),
            }

        # Validate elements
        valid_elements = []
        for elem in result.get("elements", []):
            if "bbox" in elem and len(elem["bbox"]) == 4:
                elem.setdefault("type", "other")
                elem.setdefault("label", "")
                elem.setdefault("confidence", 0.5)
                elem.setdefault("clickable", True)
                elem.setdefault("state", "enabled")
                valid_elements.append(elem)

        result["elements"] = valid_elements

        logger.info(
            "Vision analysis complete",
            extra={"element_count": len(valid_elements)},
        )

        return result
