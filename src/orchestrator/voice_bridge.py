"""OmniCompanion — Voice Bridge (WebSocket v2)

Enhanced WebSocket server for voice-first multimodal interaction.
Supports voice transcripts, TTS directives, interrupt signals,
agent-initiated messages, theme selection, and streaming status.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import websockets
    from websockets.server import serve
    HAS_WS = True
except ImportError:
    HAS_WS = False
    logger.warning("websockets not installed — voice bridge disabled")


class VoiceBridge:
    """Voice-first WebSocket bridge for multimodal companion.

    Protocol (Server → Client):
      - {"type": "speak", "text": "...", "priority": "normal|interrupt"}
      - {"type": "status", "state": "idle|listening|thinking|speaking|acting", "detail": "..."}
      - {"type": "activity", "icon": "...", "text": "...", "level": "info|success|error"}
      - {"type": "companion_message", "text": "...", "has_action": bool}
      - {"type": "action_result", "action": "...", "success": bool, "detail": "..."}
      - {"type": "theme_applied", "theme": "...", "greeting": "..."}
      - {"type": "welcome", "message": "..."}

    Protocol (Client → Server):
      - {"type": "voice_transcript", "text": "...", "is_final": bool}
      - {"type": "interrupt"}
      - {"type": "message", "text": "..."}
      - {"type": "select_theme", "theme": "professional|friendly|playful|minimal"}
      - {"type": "command", "action": "..."}
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.clients: set = set()
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self._server = None
        self.current_theme: str = "friendly"
        self._interrupted = False

    @property
    def interrupted(self) -> bool:
        return self._interrupted

    def clear_interrupt(self):
        self._interrupted = False

    async def start(self) -> None:
        """Start the WebSocket server."""
        if not HAS_WS:
            logger.warning("Voice bridge not started — websockets not installed")
            return

        self._server = await serve(
            self._handler,
            self.host,
            self.port,
        )
        logger.info(f"Voice bridge listening on ws://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("Voice bridge stopped")

    async def _handler(self, websocket) -> None:
        """Handle a new WebSocket connection."""
        self.clients.add(websocket)
        client_id = id(websocket)
        logger.info(f"Client connected (id={client_id})")

        # Send welcome — UI should show onboarding if first time
        await self._send(websocket, {
            "type": "welcome",
            "message": "Connected to OmniCompanion engine",
            "available_themes": ["professional", "friendly", "playful", "minimal"],
        })

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._handle_message(data, websocket)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from client: {message[:100]}")
        except Exception as e:
            logger.debug(f"Client disconnected: {e}")
        finally:
            self.clients.discard(websocket)
            logger.info(f"Client disconnected (id={client_id})")

    async def _handle_message(self, data: dict, websocket) -> None:
        """Handle incoming message from the UI."""
        msg_type = data.get("type", "")

        if msg_type == "voice_transcript":
            # Voice input from browser STT
            text = data.get("text", "").strip()
            is_final = data.get("is_final", True)

            if text and is_final:
                logger.info(f"Voice transcript: {text}")
                await self.message_queue.put(text)
            elif text and not is_final:
                # Interim transcript — could be used for interrupt detection
                logger.debug(f"Interim transcript: {text}")

        elif msg_type == "interrupt":
            # User started speaking — interrupt agent's TTS
            logger.info("Interrupt signal received")
            self._interrupted = True

        elif msg_type in ("message", "goal"):
            # Text message (from chat panel or legacy)
            text = data.get("text", "").strip()
            if text:
                logger.info(f"Text message: {text}")
                await self.message_queue.put(text)

        elif msg_type == "select_theme":
            # User selected a personality theme
            theme = data.get("theme", "friendly")
            self.current_theme = theme
            logger.info(f"Theme selected: {theme}")

            from src.orchestrator.gemini.prompts_v2 import PERSONALITY_THEMES
            theme_data = PERSONALITY_THEMES.get(theme, PERSONALITY_THEMES["friendly"])

            await self.broadcast({
                "type": "theme_applied",
                "theme": theme,
                "greeting": theme_data["greeting"],
                "colors": {
                    "primary": theme_data["color_primary"],
                    "accent": theme_data["color_accent"],
                },
            })

            # Queue the theme selection as a system message for the companion
            await self.message_queue.put(f"__theme__{theme}")

        elif msg_type == "command":
            action = data.get("action", "")
            logger.info(f"Command: {action}")
            await self.message_queue.put(f"__cmd__{action}")

    async def _send(self, websocket, data: dict) -> None:
        """Send JSON message to a specific client."""
        try:
            await websocket.send(json.dumps(data))
        except Exception:
            pass

    async def broadcast(self, data: dict) -> None:
        """Broadcast a message to all connected clients."""
        if not self.clients:
            return
        message = json.dumps(data)
        dead = set()
        for ws in self.clients:
            try:
                await ws.send(message)
            except Exception:
                dead.add(ws)
        self.clients -= dead

    def has_clients(self) -> bool:
        return len(self.clients) > 0

    # ──────────────────────────────────────
    # High-level send methods
    # ──────────────────────────────────────

    async def speak(self, text: str, priority: str = "normal") -> None:
        """Tell the browser to speak text via TTS."""
        await self.broadcast({
            "type": "speak",
            "text": text,
            "priority": priority,
            "timestamp": time.time(),
        })

    async def send_companion_message(
        self, text: str, has_action: bool = False
    ) -> None:
        """Send companion's text response (for chat panel + activity)."""
        await self.broadcast({
            "type": "companion_message",
            "text": text,
            "has_action": has_action,
            "timestamp": time.time(),
        })

    async def send_status(self, state: str, detail: str = "") -> None:
        """Update agent state on UI (drives orb animation)."""
        await self.broadcast({
            "type": "status",
            "state": state,
            "detail": detail,
        })

    async def send_activity(
        self, text: str, icon: str = "⚡", level: str = "info"
    ) -> None:
        """Send an activity feed entry."""
        await self.broadcast({
            "type": "activity",
            "icon": icon,
            "text": text,
            "level": level,
            "timestamp": time.time(),
        })

    async def send_action_result(
        self, action_type: str, success: bool, detail: str = ""
    ) -> None:
        """Notify UI about action result."""
        await self.broadcast({
            "type": "action_result",
            "action": action_type,
            "success": success,
            "detail": detail,
            "timestamp": time.time(),
        })

    async def send_log(
        self, agent: str, message: str, status: str = "info"
    ) -> None:
        """Send a log entry (backward compatible)."""
        await self.broadcast({
            "type": "log",
            "agent": agent,
            "message": message,
            "status": status,
            "timestamp": time.time(),
        })
