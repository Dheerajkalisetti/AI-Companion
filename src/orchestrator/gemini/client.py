"""OmniCompanion — Gemini Client (Vertex AI Wrapper)

Production-grade wrapper around Vertex AI SDK for Gemini 1.5 Pro.
Handles authentication, multimodal input, streaming, retry logic,
and token counting.
"""

from __future__ import annotations

import os
import io
import logging
from typing import Any, Optional, Union

import vertexai
from vertexai.generative_models import (
    GenerativeModel,
    GenerationConfig,
    HarmCategory,
    HarmBlockThreshold,
    Part,
    Image,
)
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from google.api_core.exceptions import (
    ResourceExhausted,
    ServiceUnavailable,
    DeadlineExceeded,
    InvalidArgument,
    PermissionDenied,
)
from PIL import Image as PILImage

logger = logging.getLogger(__name__)


# Default safety configuration
SAFETY_CONFIG = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
}


class GeminiClient:
    """Production-grade Gemini 1.5 Pro client via Vertex AI.

    Features:
    - Text and multimodal (image + text) generation
    - Streaming responses
    - Retry logic with exponential backoff
    - Token counting and context window management
    - Configurable safety settings
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        model_id: str = "gemini-3-flash-preview",
        max_output_tokens: int = 8192,
        temperature: float = 0.1,
        top_p: float = 0.95,
        top_k: int = 40,
    ) -> None:
        """Initialize the Gemini client.

        Args:
            project_id: GCP project ID. Defaults to GCP_PROJECT_ID env var.
            location: Vertex AI location. Defaults to VERTEX_AI_LOCATION env var.
            model_id: Gemini model identifier.
            max_output_tokens: Maximum tokens in response.
            temperature: Sampling temperature (0.0 = deterministic).
            top_p: Nucleus sampling parameter.
            top_k: Top-k sampling parameter.
        """
        self.project_id = project_id or os.environ.get("GCP_PROJECT_ID", "")
        self.location = location or os.environ.get("VERTEX_AI_LOCATION", "us-central1")
        self.model_id = model_id
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k

        # Initialize Vertex AI
        vertexai.init(project=self.project_id, location=self.location)
        self.model = GenerativeModel(self.model_id)

        # Default generation config
        self.default_config = GenerationConfig(
            max_output_tokens=self.max_output_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
            top_k=self.top_k,
        )

        logger.info(
            "GeminiClient initialized",
            extra={
                "project_id": self.project_id,
                "location": self.location,
                "model_id": self.model_id,
            },
        )

    @staticmethod
    def prepare_screenshot(raw_bytes: bytes, max_dim: int = 3072) -> bytes:
        """Prepare screenshot for Gemini multimodal input.

        Resizes image if too large for optimal performance.

        Args:
            raw_bytes: Raw PNG/JPEG image bytes.
            max_dim: Maximum dimension (width or height).

        Returns:
            Optimized PNG bytes.
        """
        img = PILImage.open(io.BytesIO(raw_bytes))

        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), PILImage.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(
            (ResourceExhausted, ServiceUnavailable, DeadlineExceeded)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        response_mime_type: str = "application/json",
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Generate text response from a text prompt.

        Args:
            prompt: The text prompt.
            system_instruction: Optional system instruction.
            response_mime_type: Response format (application/json or text/plain).
            max_output_tokens: Override default max tokens.
            temperature: Override default temperature.

        Returns:
            Generated text response.

        Raises:
            InvalidArgument: If prompt is malformed.
            PermissionDenied: If authentication fails.
        """
        config = GenerationConfig(
            max_output_tokens=max_output_tokens or self.max_output_tokens,
            temperature=temperature if temperature is not None else self.temperature,
            top_p=self.top_p,
            top_k=self.top_k,
            response_mime_type=response_mime_type,
        )

        model = self.model
        if system_instruction:
            model = GenerativeModel(
                self.model_id,
                system_instruction=[system_instruction],
            )

        response = model.generate_content(
            contents=[prompt],
            generation_config=config,
            safety_settings=SAFETY_CONFIG,
        )

        logger.info(
            "Gemini text generation complete",
            extra={
                "prompt_length": len(prompt),
                "response_length": len(response.text) if response.text else 0,
            },
        )

        return response.text

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(
            (ResourceExhausted, ServiceUnavailable, DeadlineExceeded)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def generate_multimodal(
        self,
        image_bytes: bytes,
        text_prompt: str,
        system_instruction: Optional[str] = None,
        response_mime_type: str = "application/json",
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Generate response from image + text multimodal input.

        Args:
            image_bytes: PNG/JPEG image bytes.
            text_prompt: Text prompt to accompany the image.
            system_instruction: Optional system instruction.
            response_mime_type: Response format.
            max_output_tokens: Override default max tokens.
            temperature: Override default temperature.

        Returns:
            Generated text response.
        """
        # Prepare image
        optimized_bytes = self.prepare_screenshot(image_bytes)
        image_part = Part.from_image(Image.from_bytes(optimized_bytes))

        config = GenerationConfig(
            max_output_tokens=max_output_tokens or self.max_output_tokens,
            temperature=temperature if temperature is not None else self.temperature,
            top_p=self.top_p,
            top_k=self.top_k,
            response_mime_type=response_mime_type,
        )

        model = self.model
        if system_instruction:
            model = GenerativeModel(
                self.model_id,
                system_instruction=[system_instruction],
            )

        response = model.generate_content(
            contents=[image_part, text_prompt],
            generation_config=config,
            safety_settings=SAFETY_CONFIG,
        )

        logger.info(
            "Gemini multimodal generation complete",
            extra={
                "image_size_bytes": len(optimized_bytes),
                "prompt_length": len(text_prompt),
                "response_length": len(response.text) if response.text else 0,
            },
        )

        return response.text

    async def generate_streaming(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
    ):
        """Generate streaming text response.

        Yields text chunks as they arrive.

        Args:
            prompt: The text prompt.
            system_instruction: Optional system instruction.
            max_output_tokens: Override default max tokens.

        Yields:
            Text chunks as strings.
        """
        config = GenerationConfig(
            max_output_tokens=max_output_tokens or self.max_output_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
            top_k=self.top_k,
        )

        model = self.model
        if system_instruction:
            model = GenerativeModel(
                self.model_id,
                system_instruction=[system_instruction],
            )

        response_stream = model.generate_content(
            contents=[prompt],
            generation_config=config,
            safety_settings=SAFETY_CONFIG,
            stream=True,
        )

        for chunk in response_stream:
            if chunk.text:
                yield chunk.text

    def count_tokens(self, contents: Union[str, list]) -> int:
        """Count tokens in the given content.

        Args:
            contents: Text string or list of content parts.

        Returns:
            Total token count.
        """
        if isinstance(contents, str):
            contents = [contents]

        token_count = self.model.count_tokens(contents)
        return token_count.total_tokens
