"""OmniCompanion — Action Executor Agent

Translates action commands into OS-level inputs via the Rust gRPC layer.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

try:
    import grpc
    HAS_GRPC = True
except ImportError:
    grpc = None
    HAS_GRPC = False

logger = logging.getLogger(__name__)


class ActionExecutorAgent:
    """Agent 3: OS-level action execution via Rust gRPC.

    Input: {type: click|type|scroll|key, target, value}
    Output: {success: bool, error: str|null, screenshot_after: bytes}
    """

    def __init__(
        self,
        grpc_host: str = "127.0.0.1",
        grpc_port: int = 50051,
    ) -> None:
        self.name = "action_executor"
        self.grpc_host = grpc_host
        self.grpc_port = grpc_port
        self.channel = None
        self.stub = None

    async def connect(self) -> None:
        """Establish gRPC connection to Rust system layer."""
        if not HAS_GRPC:
            logger.warning("gRPC not available — running in test mode")
            return
        address = f"{self.grpc_host}:{self.grpc_port}"
        self.channel = grpc.insecure_channel(address)
        logger.info(f"ActionExecutor connected to Rust layer at {address}")

    async def disconnect(self) -> None:
        """Close gRPC connection."""
        if self.channel:
            self.channel.close()
            logger.info("ActionExecutor disconnected from Rust layer")

    async def execute(self, action: dict) -> dict:
        """Execute an OS-level action via the Rust system layer.

        Args:
            action: Action command JSON with type, target, value.

        Returns:
            Execution result with success status and optional screenshot.
        """
        action_type = action.get("action_type", action.get("type", ""))

        try:
            if action_type in ("click", "double_click", "right_click"):
                return await self._execute_mouse(action)
            elif action_type == "type":
                return await self._execute_keyboard_type(action)
            elif action_type in ("key", "hotkey"):
                return await self._execute_keyboard_key(action)
            elif action_type == "scroll":
                return await self._execute_scroll(action)
            elif action_type == "wait":
                return await self._execute_wait(action)
            elif action_type == "get_hierarchy":
                return await self._get_ui_hierarchy(action)
            elif action_type == "click_by_name":
                return await self._execute_click_by_name(action)
            elif action_type == "wait_for_app":
                return await self._execute_wait_for_app(action)
            elif action_type == "request_permissions":
                return await self._execute_request_permissions(action)
            elif action_type == "open_url":
                return await self._execute_open_url(action)
            elif action_type == "hotkey":
                return await self._execute_keyboard_key(action) # Re-use key handler
            elif action_type in ("command", "sh", "bash", "terminal"):
                return await self._execute_terminal_command(action)
            else:
                return {
                    "success": False,
                    "error": f"Unknown action type: {action_type}",
                    "screenshot_after": None,
                }
        except Exception as e:
            if HAS_GRPC and isinstance(e, grpc.RpcError):
                logger.error(f"gRPC error executing action: {e}")
                return {
                    "success": False,
                    "error": f"gRPC error: {e.code()}: {e.details()}",
                    "screenshot_after": None,
                }
            logger.error(f"Error executing action: {e}")
            return {
                "success": False,
                "error": str(e),
                "screenshot_after": None,
            }

    async def _execute_mouse(self, action: dict) -> dict:
        """Execute mouse action using AppleScript."""
        target = action.get("target", {})
        x = target.get("x")
        y = target.get("y")

        if x is None or y is None:
            return {
                "success": False,
                "error": "Mouse click required coordinates (x, y) but none were provided.",
                "screenshot_after": None,
            }

        logger.info(f"Mouse click at ({x}, {y}) via AppleScript...")

        script = f"""
        tell application "System Events"
            click at {{{x}, {y}}}
        end tell
        """

        try:
            process = await asyncio.create_subprocess_exec(
                "osascript", "-e", script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return {
                    "success": True,
                    "error": None,
                    "action_performed": {"type": "click", "x": x, "y": y},
                    "screenshot_after": None,
                }
            else:
                error_msg = stderr.decode().strip()
                if "not allowed to send keystrokes" in error_msg.lower() or "System Events" in error_msg:
                    error_msg = "Accessibility permissions missing. Please enable in Settings -> Privacy -> Accessibility."
                return {
                    "success": False,
                    "error": f"AppleScript click failed: {error_msg}",
                    "action_performed": {"type": "click", "x": x, "y": y},
                    "screenshot_after": None,
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "action_performed": {"type": "click", "x": x, "y": y},
                "screenshot_after": None,
            }

    async def _execute_keyboard_type(self, action: dict) -> dict:
        """Execute keyboard typing using AppleScript."""
        value = action.get("value", "")
        if not value:
            return {"success": False, "error": "No value provided for typing"}

        # Escape quotes for AppleScript
        escaped_value = value.replace('"', '\\"')
        logger.info(f"Keyboard type: '{value[:20]}...' via AppleScript")

        script = f"""
        tell application "System Events"
            keystroke "{escaped_value}"
        end tell
        """

        try:
            process = await asyncio.create_subprocess_exec(
                "osascript", "-e", script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return {
                    "success": True,
                    "error": None,
                    "action_performed": {"type": "type", "value": value},
                    "screenshot_after": None,
                }
            else:
                error_msg = stderr.decode().strip()
                return {
                    "success": False,
                    "error": f"AppleScript typing failed: {error_msg}",
                    "action_performed": {"type": "type", "value": value},
                    "screenshot_after": None,
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "action_performed": {"type": "type", "value": value},
                "screenshot_after": None,
            }

    async def _execute_keyboard_key(self, action: dict) -> dict:
        """Execute keyboard key press using AppleScript key codes."""
        key = action.get("key", "").lower()
        modifiers = action.get("modifiers", [])

        # Common AppleScript key codes
        key_codes = {
            "enter": 36,
            "return": 36,
            "tab": 48,
            "space": 49,
            "backspace": 51,
            "delete": 51,
            "escape": 53,
            "esc": 53,
            "command": 55,
            "shift": 56,
            "caps": 57,
            "option": 58,
            "control": 59,
            "right_shift": 60,
            "right_option": 61,
            "right_control": 62,
            "function": 63,
            "volume_up": 72,
            "volume_down": 73,
            "mute": 74,
            "f1": 122,
            "f2": 120,
            "f3": 99,
            "f4": 118,
            "f5": 96,
            "f6": 97,
            "f7": 98,
            "f8": 100,
            "f9": 101,
            "f10": 109,
            "f11": 103,
            "f12": 111,
            "help": 114,
            "home": 115,
            "page_up": 116,
            "forward_delete": 117,
            "end": 119,
            "page_down": 121,
            "up_arrow": 126,
            "down_arrow": 125,
            "left_arrow": 123,
            "right_arrow": 124,
            "up": 126,
            "down": 125,
            "left": 123,
            "right": 124,
        }

        modifier_map = {
            "command": "command down",
            "control": "control down",
            "option": "option down",
            "alt": "option down",
            "shift": "shift down",
        }

        logger.info(f"Keyboard key: {'+'.join(modifiers + [key])} via AppleScript")

        if key in key_codes:
            code = key_codes[key]
            mods = ", ".join([modifier_map[m] for m in modifiers if m in modifier_map])
            using_clause = f" using {{{mods}}}" if mods else ""
            script = f'tell application "System Events" to key code {code}{using_clause}'
        else:
            # Fallback to keystroke for single characters
            escaped_key = key.replace('"', '\\"')
            mods = ", ".join([modifier_map[m] for m in modifiers if m in modifier_map])
            using_clause = f" using {{{mods}}}" if mods else ""
            script = f'tell application "System Events" to keystroke "{escaped_key}"{using_clause}'

        try:
            process = await asyncio.create_subprocess_exec(
                "osascript", "-e", script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return {
                    "success": True,
                    "error": None,
                    "action_performed": {"type": "key", "key": key, "modifiers": modifiers},
                    "screenshot_after": None,
                }
            else:
                error_msg = stderr.decode().strip()
                return {
                    "success": False,
                    "error": f"AppleScript key failed: {error_msg}",
                    "action_performed": {"type": "key", "key": key, "modifiers": modifiers},
                    "screenshot_after": None,
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "action_performed": {"type": "key", "key": key, "modifiers": modifiers},
                "screenshot_after": None,
            }

    async def _execute_scroll(self, action: dict) -> dict:
        """Execute scroll action via AppleScript."""
        delta_x = action.get("delta_x", 0)
        delta_y = action.get("delta_y", 0)
        # Positive delta_y = scroll down, negative = scroll up
        direction = "down" if delta_y > 0 else "up"
        amount = abs(delta_y) // 100 or 3  # Convert pixels to reasonable scroll amount

        logger.info(f"Scroll: {direction} by {amount} via AppleScript")

        script = f"""
        tell application "System Events"
            repeat {amount} times
                scroll {direction}
                delay 0.05
            end repeat
        end tell
        """

        try:
            process = await asyncio.create_subprocess_exec(
                "osascript", "-e", script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return {
                    "success": True,
                    "error": None,
                    "action_performed": {"type": "scroll", "delta_x": delta_x, "delta_y": delta_y},
                    "screenshot_after": None,
                }
            else:
                error_msg = stderr.decode().strip()
                return {
                    "success": False,
                    "error": f"AppleScript scroll failed: {error_msg}",
                    "action_performed": {"type": "scroll", "delta_x": delta_x, "delta_y": delta_y},
                    "screenshot_after": None,
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "action_performed": {"type": "scroll", "delta_x": delta_x, "delta_y": delta_y},
                "screenshot_after": None,
            }

    async def _execute_wait(self, action: dict) -> dict:
        """Execute a wait/sleep action."""
        # Defensive: try to get seconds from 'seconds' or 'value'
        val = action.get("seconds", action.get("value", 2))
        try:
            seconds = float(val)
        except (ValueError, TypeError):
            # Fallback for when current Planner sends a description string as 'value'
            logger.warning(f"Could not parse wait time '{val}', defaulting to 2s")
            seconds = 2.0
            
        logger.info(f"Waiting for {seconds}s...")
        await asyncio.sleep(seconds)
        return {
            "success": True,
            "error": None,
            "action_performed": {"type": "wait", "seconds": seconds},
            "screenshot_after": None,
        }

    async def _get_ui_hierarchy(self, action: dict) -> dict:
        """Get accessibility hierarchy via a robust, deep-scanning AppleScript."""
        script = """
        set elementList to ""
        try
            tell application "System Events"
                set frontAppProcess to first application process whose frontmost is true
                tell frontAppProcess
                    set winCount to count of windows
                    if winCount is 0 then return "NO_WINDOWS"
                    
                    set theWindow to front window
                    set elementList to "WINDOW: " & (name of theWindow) & "\n"
                    
                    -- Optimized search for browsers (Chrome/Safari)
                    set appName to name
                    if appName contains "Chrome" or appName contains "Safari" or appName contains "Edge" then
                        -- Browser specific: capture web content area
                        try
                            set webArea to (first UI element of front window whose role is "AXWebArea")
                            repeat with theElem in (every UI element of webArea whose role is "AXButton" or role is "AXTextField" or role is "AXLink" or role is "AXStaticText")
                                try
                                    set eName to name of theElem
                                    if eName is not missing value and eName is not "" then
                                        set elementList to elementList & (role of theElem) & ": '" & eName & "'\n"
                                    end if
                                end try
                            end repeat
                        on error
                            -- Fallback to standard window scan if AXWebArea fails
                        end try
                    end if
                    
                    -- Capture standard common interactive elements
                    repeat with theElem in (every UI element of theWindow whose role is "button" or role is "text field" or role is "menu item" or role is "static text" or role is "search field")
                        try
                            set eName to name of theElem
                            set eRole to role of theElem
                            if eName is not missing value and eName is not "" then
                                set elementList to elementList & eRole & ": '" & eName & "'\n"
                            end if
                        end try
                    end repeat
                end tell
            end tell
        on error errMsg
            return "ERROR: " & errMsg
        end try
        return elementList
        """
        
        logger.info("Fetching OS-level UI hierarchy...")
        
        try:
            process = await asyncio.create_subprocess_exec(
                "osascript", "-e", script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            output = stdout.decode().strip()
            if process.returncode == 0 and not output.startswith("ERROR:"):
                return {
                    "success": True,
                    "error": None,
                    "action_performed": {"type": "get_hierarchy"},
                    "hierarchy": output,
                    "screenshot_after": None,
                }
            else:
                error_msg = output if output.startswith("ERROR:") else stderr.decode().strip()
                if "not allowed to send keystrokes" in error_msg.lower() or "System Events" in error_msg:
                    error_msg = "Accessibility permissions missing. Please enable in Settings -> Privacy -> Accessibility."
                
                return {
                    "success": False,
                    "error": error_msg,
                    "action_performed": {"type": "get_hierarchy"},
                    "screenshot_after": None,
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "action_performed": {"type": "get_hierarchy"},
                "screenshot_after": None,
            }

    async def _execute_click_by_name(self, action: dict) -> dict:
        """Click a UI element by its accessibility name via AppleScript."""
        name = action.get("value", action.get("name", ""))
        role = action.get("role", "UI element")
        
        if not name:
            return {"success": False, "error": "No name provided for click_by_name"}

        script = f"""
        tell application "System Events"
            set frontApp to name of first application process whose frontmost is true
            tell process frontApp
                try
                    click (first UI element whose name is "{name}")
                    return "SUCCESS"
                on error
                    try
                        -- Try deep search in windows
                        repeat with theWindow in every window
                            try
                                click (first UI element of theWindow whose name is "{name}")
                                return "SUCCESS"
                            end try
                        end repeat
                    on error errMsg
                        return "ERROR: " & errMsg
                    end try
                end try
            end tell
        end tell
        """
        
        logger.info(f"Attempting to click '{name}' ({role}) via AppleScript...")
        
        try:
            process = await asyncio.create_subprocess_exec(
                "osascript", "-e", script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            output = stdout.decode().strip()
            if "SUCCESS" in output:
                return {
                    "success": True,
                    "error": None,
                    "action_performed": {"type": "click_by_name", "name": name},
                    "screenshot_after": None,
                }
            else:
                error_msg = output if output.startswith("ERROR:") else stderr.decode().strip()
                return {
                    "success": False,
                    "error": f"Could not find or click element '{name}': {error_msg}",
                    "action_performed": {"type": "click_by_name", "name": name},
                    "screenshot_after": None,
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "action_performed": {"type": "click_by_name", "name": name},
                "screenshot_after": None,
            }

    async def _execute_terminal_command(self, action: dict) -> dict:
        """Execute a terminal command."""
        command = action.get("command", action.get("value", ""))
        
        # Security: block clearly dangerous commands even in execution
        dangerous = ["rm -rf /", "mkfs", "> /dev/sda", "dd if="]
        if any(d in command for d in dangerous):
            return {
                "success": False,
                "error": "Command blocked by security policy",
                "action_performed": {"type": "command", "command": command},
                "screenshot_after": None,
            }

        logger.info(f"Executing command: {command}")
        
        try:

            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            output = stdout.decode().strip()
            error_output = stderr.decode().strip()
            
            if process.returncode == 0:
                return {
                    "success": True,
                    "error": None,
                    "action_performed": {"type": "command", "command": command},
                    "output": output or "Command executed successfully (no output)",
                    "screenshot_after": None,
                }
            else:
                return {
                    "success": False,
                    "error": error_output or "Command failed with generic error",
                    "action_performed": {"type": "command", "command": command},
                    "output": output,
                    "screenshot_after": None,
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "action_performed": {"type": "command", "command": command},
                "screenshot_after": None,
            }

    async def _execute_wait_for_app(self, action: dict) -> dict:
        """Poll until an app is frontmost and has windows."""
        app_name = action.get("value", action.get("app_name", ""))
        if not app_name:
            return {"success": False, "error": "No app_name provided"}
            
        timeout = float(action.get("timeout", 10.0))
        interval = 1.0
        elapsed = 0.0
        
        script = """
        try
            tell application "System Events"
                set frontProcess to first application process whose frontmost is true
                set frontName to name of frontProcess
                set windowCount to count of windows of frontProcess
                return frontName & "|" & windowCount
            end tell
        on error
            return "ERROR"
        end try
        """
        
        logger.info(f"Waiting for app '{app_name}' to be frontmost...")
        
        while elapsed < timeout:
            process = await asyncio.create_subprocess_exec(
                "osascript", "-e", script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            output = stdout.decode().strip()
            
            if "|" in output:
                name, count = output.split("|")
                if app_name.lower() in name.lower() and int(count) > 0:
                    return {
                        "success": True, 
                        "error": None, 
                        "action_performed": {"type": "wait_for_app", "app": name}
                    }
            
            await asyncio.sleep(interval)
            elapsed += interval
            
        return {
            "success": False, 
            "error": f"Timeout waiting for app '{app_name}' to be ready",
            "action_performed": {"type": "wait_for_app", "app": app_name}
        }

    async def _execute_request_permissions(self, action: dict) -> dict:
        """Open System Settings to the Screen Recording permission page."""
        script = 'open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"'
        logger.info("Proactively requesting Screen Recording permissions...")
        
        try:
            process = await asyncio.create_subprocess_shell(script)
            await process.wait()
            return {
                "success": True,
                "error": None,
                "action_performed": {"type": "request_permissions"},
                "message": "Opened System Settings. Please enable Screen Recording for Terminal/Python."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _execute_open_url(self, action: dict) -> dict:
        """Open a URL in a browser using the OS 'open' command."""
        url = action.get("url", action.get("value", ""))
        browser = action.get("browser", "Google Chrome")
        
        if not url:
            return {"success": False, "error": "No URL provided"}
        
        # Ensure URL has a protocol
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        logger.info(f"Opening URL '{url}' in {browser}...")
        
        # Command: open -a "Browser" "URL"
        command = f'open -a "{browser}" "{url}"'
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.wait()
            
            if process.returncode == 0:
                return {
                    "success": True,
                    "error": None,
                    "action_performed": {"type": "open_url", "url": url, "browser": browser}
                }
            else:
                stderr = (await process.stderr.read()).decode().strip()
                return {"success": False, "error": stderr or f"Failed to open URL with {browser}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def capture_screen(self) -> Optional[bytes]:
        """Capture a screenshot using macOS native screencapture.

        Returns:
            PNG screenshot bytes, or None on failure.
        """
        try:
            from src.orchestrator.vision.screen_capture import capture_screen_macos
            screenshot = capture_screen_macos()
            if screenshot:
                logger.info(f"Screen captured: {len(screenshot):,} bytes")
            else:
                logger.warning("Screen capture returned None (permissions?)")
            return screenshot
        except Exception as e:
            logger.error(f"Screen capture failed: {e}")
            return None
