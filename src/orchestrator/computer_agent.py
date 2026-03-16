"""OmniCompanion — Computer Use Agent

Uses Gemini Computer Use Preview model to see the screen via screenshots
and control the computer via PyAutoGUI. This is the ACTION layer of the
multi-model pipeline.

Flow:
  1. Receives a task/goal as text
  2. Takes a screenshot of the current screen
  3. Sends screenshot + goal to Computer Use model
  4. Model outputs UI actions (click_at, type_text_at, etc.)
  5. Executes actions via PyAutoGUI
  6. Takes new screenshot, sends back → repeat until done

Supported actions: click_at, type_text_at, key_combination, scroll_at,
scroll_document, navigate, hover_at, drag_and_drop, open_web_browser,
go_back, go_forward, search, wait_5_seconds
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import subprocess
import time
from typing import Any

logger = logging.getLogger("omnicompanion.computer_agent")

# ─── PyAutoGUI Setup ──────────────────────────────────
try:
    import pyautogui
    pyautogui.FAILSAFE = True  # Move mouse to corner to abort
    pyautogui.PAUSE = 0.3      # Brief pause between actions
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False
    logger.warning("pyautogui not installed. Run: pip install pyautogui")

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from google import genai
from google.genai import types
from google.genai.types import Content, Part

# ─── Constants ────────────────────────────────────────

# Planning model — fast, cheap, no CU rate limits. Used to generate full action plans.
PLANNER_MODEL = "gemini-2.5-flash"
# Computer Use model — fallback if planner doesn't have enough screen context.
CU_FALLBACK_MODELS = [
    "gemini-2.5-computer-use-preview-10-2025",
    "gemini-3-flash-preview",
]

MAX_RETRIES = 3
RETRY_DELAY = 10
API_TIMEOUT = 30

# JSON schema for the planning model response
PLAN_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING"},
            "args": {"type": "OBJECT"}
        },
        "required": ["action"]
    }
}


# ─── Screen Utilities ─────────────────────────────────

def get_screen_size() -> tuple[int, int]:
    """Get the actual screen size."""
    if HAS_PYAUTOGUI:
        return pyautogui.size()
    # Fallback for macOS
    try:
        output = subprocess.check_output(
            ["system_profiler", "SPDisplaysDataType"],
            text=True,
        )
        for line in output.split("\n"):
            if "Resolution" in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == "x" and i > 0 and i < len(parts) - 1:
                        return int(parts[i - 1]), int(parts[i + 1])
    except Exception:
        pass
    return 1440, 900  # Default


def take_screenshot() -> bytes | None:
    """Capture the full screen as PNG bytes."""
    try:
        tmp_path = "/tmp/_omni_screenshot.png"
        subprocess.run(
            ["screencapture", "-x", "-C", tmp_path],
            check=True,
            capture_output=True,
        )
        with open(tmp_path, "rb") as f:
            data = f.read()
        os.remove(tmp_path)
        if len(data) > 100:
            return data
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
    return None


async def wait_for_screen_stable(max_wait: float = 8.0, interval: float = 0.5, threshold: int = 5000) -> bytes | None:
    """Wait until the screen stops changing, then return the stable screenshot.

    Compares consecutive screenshot sizes — when they differ by less than
    `threshold` bytes, the screen is considered stable.

    Args:
        max_wait: Maximum seconds to wait
        interval: Seconds between screenshot checks
        threshold: Byte-size difference below which screen is 'stable'

    Returns:
        The stable screenshot bytes, or the last screenshot taken.
    """
    prev_screenshot = take_screenshot()
    if not prev_screenshot:
        return None

    elapsed = 0.0
    while elapsed < max_wait:
        await asyncio.sleep(interval)
        elapsed += interval
        curr_screenshot = take_screenshot()
        if not curr_screenshot:
            return prev_screenshot

        # Compare sizes — if similar, screen has stabilized
        diff = abs(len(curr_screenshot) - len(prev_screenshot))
        if diff < threshold:
            return curr_screenshot

        prev_screenshot = curr_screenshot

    return prev_screenshot


def denormalize_x(x: int, screen_width: int) -> int:
    """Convert normalized x (0–1000) to actual pixel coordinate."""
    return int(x / 1000 * screen_width)


def denormalize_y(y: int, screen_height: int) -> int:
    """Convert normalized y (0–1000) to actual pixel coordinate."""
    return int(y / 1000 * screen_height)


# ─── Action Executor ──────────────────────────────────

async def execute_ui_action(
    func_name: str,
    args: dict,
    screen_width: int,
    screen_height: int,
) -> dict:
    """Execute a single UI action from the Computer Use model.

    Returns: {"result": "description"} or {"error": "description"}
    """
    if not HAS_PYAUTOGUI:
        return {"error": "pyautogui not installed"}

    try:
        if func_name == "open_app":
            app_name = args.get("name", "")
            subprocess.Popen(["open", "-a", app_name])
            await asyncio.sleep(1)  # Wait for app to launch
            return {"result": f"Opened {app_name}"}

        elif func_name == "open_web_browser":
            # Detect and activate the frontmost browser, or open Chrome
            front_app = _get_frontmost_app()
            browsers = ("Safari", "Google Chrome", "Firefox", "Arc", "Brave Browser", "Microsoft Edge")
            if front_app in browsers:
                subprocess.Popen(["open", "-a", front_app])
                return {"result": f"Activated {front_app}"}
            else:
                subprocess.Popen(["open", "-a", "Google Chrome"])
                return {"result": "Opened Google Chrome"}

        elif func_name == "navigate":
            url = args.get("url", "")
            # Navigate in the frontmost browser's active tab via AppleScript
            front_app = _get_frontmost_app()
            browsers = ("Safari", "Google Chrome", "Firefox", "Arc", "Brave Browser", "Microsoft Edge")
            if front_app in browsers:
                if front_app == "Safari":
                    script = f'tell application "Safari" to set URL of current tab of front window to "{url}"'
                elif front_app == "Google Chrome":
                    script = f'tell application "Google Chrome" to set URL of active tab of front window to "{url}"'
                else:
                    # Fallback: use the address bar
                    pyautogui.hotkey("command", "l")
                    await asyncio.sleep(0.2)
                    pyautogui.hotkey("command", "a")
                    pyautogui.typewrite(url, interval=0.01)
                    pyautogui.press("enter")
                    return {"result": f"Navigated to {url}"}
                subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
                return {"result": f"Navigated to {url}"}
            else:
                # No browser is frontmost — open URL in Chrome
                subprocess.Popen(["open", "-a", "Google Chrome", url])
                return {"result": f"Opened {url} in Google Chrome"}

        elif func_name == "click_at":
            point = args.get("point", [500, 500])
            x = denormalize_x(point[1], screen_width)
            y = denormalize_y(point[0], screen_height)
            pyautogui.click(x, y)
            return {"result": f"Clicked at ({x}, {y})"}

        elif func_name == "hover_at":
            point = args.get("point", [500, 500])
            x = denormalize_x(point[1], screen_width)
            y = denormalize_y(point[0], screen_height)
            pyautogui.moveTo(x, y)
            return {"result": f"Hovered at ({x}, {y})"}

        elif func_name == "type_text_at":
            point = args.get("point", [500, 500])
            x = denormalize_x(point[1], screen_width)
            y = denormalize_y(point[0], screen_height)
            text = args.get("text", "")
            press_enter = args.get("press_enter", False)
            clear_before = args.get("clear_before_typing", False)

            pyautogui.click(x, y)
            await asyncio.sleep(0.15)

            if clear_before:
                pyautogui.hotkey("command", "a")
                pyautogui.press("backspace")

            pyautogui.typewrite(text, interval=0.02) if text.isascii() else pyautogui.write(text)

            if press_enter:
                pyautogui.press("enter")

            return {"result": f"Typed '{text[:30]}...' at ({x}, {y})"}

        elif func_name == "key_combination":
            keys = args.get("keys", "")
            # Convert "Control+A" format to pyautogui format
            key_list = [k.strip().lower() for k in keys.split("+")]
            # Map common key names
            key_map = {
                "control": "ctrl",
                "command": "command",
                "meta": "command",
                "alt": "option",
                "option": "option",
                "shift": "shift",
                "enter": "enter",
                "return": "enter",
                "escape": "escape",
                "tab": "tab",
                "space": "space",
                "backspace": "backspace",
                "delete": "delete",
            }
            mapped = [key_map.get(k, k) for k in key_list]
            pyautogui.hotkey(*mapped)
            return {"result": f"Pressed {keys}"}

        elif func_name == "scroll_document":
            direction = args.get("direction", "down")
            scroll_amount = 5 if direction == "down" else -5
            pyautogui.scroll(scroll_amount)
            return {"result": f"Scrolled {direction}"}

        elif func_name == "scroll_at":
            point = args.get("point", [500, 500])
            x = denormalize_x(point[1], screen_width)
            y = denormalize_y(point[0], screen_height)
            direction = args.get("direction", "down")
            magnitude = args.get("magnitude", 400)
            pyautogui.moveTo(x, y)
            scroll_amount = -(magnitude // 80) if direction == "down" else (magnitude // 80)
            pyautogui.scroll(scroll_amount)
            return {"result": f"Scrolled {direction} at ({x}, {y})"}

        elif func_name == "drag_and_drop":
            start_point = args.get("start_point", [0, 0])
            end_point = args.get("end_point", [0, 0])
            x1 = denormalize_x(start_point[1], screen_width)
            y1 = denormalize_y(start_point[0], screen_height)
            x2 = denormalize_x(end_point[1], screen_width)
            y2 = denormalize_y(end_point[0], screen_height)
            pyautogui.moveTo(x1, y1)
            pyautogui.mouseDown()
            pyautogui.moveTo(x2, y2, duration=0.5)
            pyautogui.mouseUp()
            return {"result": f"Dragged ({x1},{y1}) to ({x2},{y2})"}

        elif func_name == "go_back":
            pyautogui.hotkey("command", "[")
            return {"result": "Went back"}

        elif func_name == "go_forward":
            pyautogui.hotkey("command", "]")
            return {"result": "Went forward"}

        elif func_name == "search":
            pyautogui.hotkey("command", "l")
            return {"result": "Opened search/address bar"}

        elif func_name == "wait_5_seconds":
            await asyncio.sleep(5)
            return {"result": "Waited 5 seconds"}

        elif func_name == "run_terminal_command":
            command = args.get("command", "")
            try:
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                out_str = stdout.decode().strip()
                err_str = stderr.decode().strip()
                
                result_str = f"Exit {proc.returncode}"
                if out_str: result_str += f"\nSTDOUT: {out_str[:500]}"
                if err_str: result_str += f"\nSTDERR: {err_str[:500]}"
                
                return {"result": result_str}
            except Exception as e:
                return {"error": f"Failed to execute command: {e}"}

        else:
            return {"error": f"Unknown action: {func_name}"}

    except Exception as e:
        logger.error(f"Action {func_name} failed: {e}")
        return {"error": f"{func_name} failed: {str(e)}"}


# ─── Planning System Prompt ───────────────────────────

PLANNER_SYSTEM_PROMPT = """You are a macOS desktop automation agent. Given a screenshot of the user's screen and a goal, output a JSON array of ALL actions needed to complete the goal in one go.

You can control the ENTIRE desktop — browsers, native apps (WhatsApp, Messages, Mail, Finder, Terminal, Notes, etc.), and any installed application.
Crucially, you also have direct access to the terminal.

Available actions:
- {"action": "run_terminal_command", "args": {"command": "echo 'hello' > /tmp/test.txt"}} — Run a bash/zsh command
- {"action": "open_app", "args": {"name": "WhatsApp"}} — Open any macOS app by name
- {"action": "navigate", "args": {"url": "https://..."}} — Navigate browser to URL
- {"action": "click_at", "args": {"point": [500, 500]}} — Click at a normalized spatial coordinate [y, x]
- {"action": "type_text_at", "args": {"point": [500, 500], "text": "hello", "press_enter": true, "clear_before_typing": false}} — Click at position and type text
- {"action": "key_combination", "args": {"keys": "Command+A"}} — Press key combo
- {"action": "scroll_at", "args": {"point": [500, 500], "direction": "down", "magnitude": 400}} — Scroll at position
- {"action": "scroll_document", "args": {"direction": "down"}} — Scroll the current document
- {"action": "hover_at", "args": {"point": [200, 200]}} — Move mouse to position
- {"action": "open_web_browser", "args": {}} — Open/activate the default browser
- {"action": "search", "args": {}} — Open the browser address/search bar (Cmd+L)
- {"action": "go_back", "args": {}} — Browser back
- {"action": "go_forward", "args": {}} — Browser forward
- {"action": "wait_5_seconds", "args": {}} — Wait for page/app to load

IMPORTANT RULES:
1. ALWAYS PREFER `run_terminal_command` for tasks that can be done via CLI (file management, system info, launching background processes, downloading, etc.). It is much faster and more reliable than GUI automation.
2. `point` must be a 2-element array `[y, x]` in normalized 0-1000 spatial coordinates where [0, 0] is top-left and [1000, 1000] is bottom-right. E.g., [500, 500] is the exact center. NEVER use actual pixels.
3. For desktop apps, use open_app FIRST, then click/type in the app window.
4. For browser tasks, use navigate to go to a URL directly — don't search for the website.
5. Return ALL steps needed in one JSON array. Don't return just one step.
6. Output ONLY the JSON array, no markdown, no explanation."""


# ─── Computer Use Agent ──────────────────────────────

async def run_computer_task(
    goal: str,
    api_key: str,
    on_status: callable = None,
    on_action: callable = None,
    memory_store: list = None,
) -> str:
    """Execute a computer task using a plan-then-execute architecture.

    Phase 1: Screenshot → Planner model (gemini-2.5-flash) → JSON action plan
    Phase 2: Execute all actions sequentially with PyAutoGUI
    Phase 3: Screenshot → Verify goal achieved

    This uses 2-3 API calls total instead of 10-30 with the Computer Use model.
    """
    client = genai.Client(api_key=api_key)
    screen_width, screen_height = get_screen_size()

    if on_status:
        await on_status(f"Planning: {goal[:50]}...")

    # Take initial screenshot
    screenshot_bytes = take_screenshot()
    if not screenshot_bytes:
        return "Couldn't capture screen. Screen recording permission may be needed."

    logger.info(f"Screen: {screen_width}x{screen_height}, screenshot: {len(screenshot_bytes):,} bytes")

    # ── Phase 1: Generate action plan ──
    if on_status:
        await on_status("🧠 AI is planning all steps...")

    plan = await _generate_plan(client, goal, screenshot_bytes, on_status, memory_store)
    if plan is None:
        return "Failed to generate action plan. Try again."

    if not plan:
        return "AI determined no actions are needed for this goal."

    logger.info(f"Got plan with {len(plan)} steps")
    if on_status:
        await on_status(f"📋 Got {len(plan)} steps — executing...")

    # ── Phase 2: Execute all actions ──
    for i, step in enumerate(plan):
        action = step.get("action", "")
        args = step.get("args", {})

        step_label = f"[{i + 1}/{len(plan)}]"
        logger.info(f"  {step_label} → {action}({json.dumps(args)[:60]})")
        if on_status:
            await on_status(f"{step_label} {action}")
        if on_action:
            await on_action(action, args)

        result = await execute_ui_action(action, args, screen_width, screen_height)
        result_msg = list(result.values())[0]
        logger.info(f"  {step_label} ← {result_msg[:60]}")

        if "error" in result:
            logger.warning(f"  Step {i+1} failed: {result_msg}")

        # Brief wait for UI to settle
        await asyncio.sleep(0.5)

    # ── Phase 3: Verify ──
    if on_status:
        await on_status("🔍 Verifying result...")

    verify_screenshot = await wait_for_screen_stable(max_wait=4.0, interval=0.4)
    if verify_screenshot:
        verification = await _verify_result(client, goal, verify_screenshot)
        if verification:
            logger.info(f"Verification: {verification[:120]}")
            if on_status:
                await on_status("✓ Done!")
            return verification

    if on_status:
        await on_status("✓ All steps executed!")
    return f"Executed {len(plan)} actions for: {goal}"


async def _generate_plan(client, goal: str, screenshot_bytes: bytes, on_status=None, memory_store: list = None) -> list | None:
    """Call the planner model to generate a full action plan as JSON."""
    contents = [
        Content(
            role="user",
            parts=[
                Part(text=f"Goal: {goal}"),
                Part.from_bytes(data=screenshot_bytes, mime_type="image/png"),
            ],
        )
    ]
    
    system_prompt = PLANNER_SYSTEM_PROMPT
    if memory_store:
        system_prompt += "\n\n--- YOUR MEMORY VAULT ---\nYou have previously remembered the following facts about the user:\n"
        for mem in memory_store:
            fact = mem.get("fact", "")
            context = mem.get("context", "General")
            system_prompt += f"- [{context}] {fact}\n"
        system_prompt += "Use these facts proactively to personalize your actions and decisions.\n-------------------------"

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.1,
    )

    for retry in range(MAX_RETRIES):
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.models.generate_content,
                    model=PLANNER_MODEL,
                    contents=contents,
                    config=config,
                ),
                timeout=API_TIMEOUT,
            )
            if not response.candidates:
                logger.warning("Planner returned no candidates")
                continue

            text = response.text or ""
            # Strip markdown code fences if present
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            plan = json.loads(text)
            if isinstance(plan, list):
                return plan
            else:
                logger.warning(f"Planner returned non-list: {type(plan)}")

        except json.JSONDecodeError as e:
            logger.warning(f"Planner JSON parse error: {e}")
            logger.debug(f"Raw response: {text[:200]}")
        except asyncio.TimeoutError:
            logger.warning(f"Planner timeout (attempt {retry + 1})")
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "resource_exhausted" in error_str:
                logger.warning(f"Planner rate limited, waiting {RETRY_DELAY}s...")
                if on_status:
                    await on_status(f"Rate limited, retrying in {RETRY_DELAY}s...")
                await asyncio.sleep(RETRY_DELAY)
            else:
                logger.error(f"Planner error: {e}")

    return None


async def _verify_result(client, goal: str, screenshot_bytes: bytes) -> str | None:
    """Ask the model to verify the goal was achieved from the screenshot."""
    contents = [
        Content(
            role="user",
            parts=[
                Part(text=f"I asked the computer to do this goal: {goal}\n\nLook at this screenshot. Was the goal SUCCESSFULLY achieved? Be extremely strict. You MUST see explicit visual proof on the screen that the action completed (e.g. the app is open, the message is typed, the search results match the query). If you do not see explicit proof, or if it looks like the computer is still on an intermediate step, you MUST say it failed. Respond with a brief 1-2 sentence summary of what is currently on the screen and whether it matches the exact goal."),
                Part.from_bytes(data=screenshot_bytes, mime_type="image/png"),
            ],
        )
    ]

    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model=PLANNER_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(temperature=0.1),
            ),
            timeout=15,
        )
        return response.text if response.candidates else None
    except Exception as e:
        logger.warning(f"Verification failed: {e}")
        return None


def _get_frontmost_app() -> str:
    """Get the name of the frontmost application (macOS)."""
    try:
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of first application process whose frontmost is true'],
            capture_output=True, text=True, timeout=3,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _get_current_url() -> str:
    """Get the URL of the frontmost browser tab (macOS)."""
    try:
        url_proc = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of first application process whose frontmost is true'],
            capture_output=True, text=True, timeout=3,
        )
        front_app = url_proc.stdout.strip()
        browsers = ("Safari", "Google Chrome", "Firefox", "Arc", "Brave Browser", "Microsoft Edge")
        if front_app in browsers:
            url_proc = subprocess.run(
                ["osascript", "-e",
                 f'tell application "{front_app}" to get URL of current tab of front window'],
                capture_output=True, text=True, timeout=3,
            )
            url = url_proc.stdout.strip()
            if url:
                return url
    except Exception:
        pass
    return "about:blank"

