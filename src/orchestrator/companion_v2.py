"""OmniCompanion — Companion V2 (Multi-Model Pipeline)

Three-model architecture:
  1. Gemini Native Audio Dialog — bidirectional voice
  2. Gemini 2.5 Flash — intent extraction & planning
  3. Computer Use Preview — screen control via screenshots + PyAutoGUI

The user speaks → Audio model understands → Computer agent acts → Voice narrates.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime

from dotenv import load_dotenv
from google.cloud import firestore

load_dotenv()

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("omnicompanion.v2")


# ─── Terminal Colors ──────────────────────────────────
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"


def banner():
    print(f"""
{C.CYAN}{C.BOLD}═══════════════════════════════════════════════════════
   🤖  OmniCompanion v2 — Multi-Model AI Companion
═══════════════════════════════════════════════════════{C.RESET}
{C.DIM}  Voice:  Gemini Native Audio Dialog
  Brain:  Gemini 2.5 Flash
  Actor:  Computer Use Preview + PyAutoGUI
  Just start talking — the AI hears AND acts.
  Press Ctrl+C to exit.{C.RESET}
""")


def log(agent: str, msg: str, color: str = C.WHITE):
    ts = datetime.now().strftime("%H:%M:%S")
    agent_colors = {
        "companion": C.CYAN, "system": C.DIM, "action": C.MAGENTA,
        "vision": C.BLUE, "user": C.GREEN, "error": C.RED,
        "voice": C.YELLOW, "audio": C.YELLOW, "computer": C.MAGENTA,
    }
    c = agent_colors.get(agent, color)
    print(f"  {C.DIM}{ts}{C.RESET}  {c}{agent:>10}{C.RESET}  {msg}")


# ─── PyAudio Setup ────────────────────────────────────
try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False

FORMAT = pyaudio.paInt16 if HAS_PYAUDIO else None
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

# Live API model candidates — tried in order until one connects.
# gemini-2.5-flash-native-audio-preview-12-2025 is confirmed working.
# NOTE: TTS models (preview-tts) do NOT support bidiGenerateContent.
LIVE_API_MODELS = [
    "gemini-2.5-flash-native-audio-preview-12-2025",
    "gemini-2.5-flash-exp",
]


# ─── Permission Validator ─────────────────────────────

async def validate_permissions() -> dict:
    results = {"screen_recording": False, "accessibility": False, "microphone": False}
    try:
        proc = await asyncio.create_subprocess_exec(
            "screencapture", "-x", "/tmp/_omni_perm_check.png",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()
        if os.path.exists("/tmp/_omni_perm_check.png"):
            results["screen_recording"] = os.path.getsize("/tmp/_omni_perm_check.png") > 100
            os.remove("/tmp/_omni_perm_check.png")
    except Exception:
        pass

    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", 'tell application "System Events" to get name of first process',
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        results["accessibility"] = proc.returncode == 0
    except Exception:
        pass

    if HAS_PYAUDIO:
        try:
            pya = pyaudio.PyAudio()
            stream = pya.open(format=FORMAT, channels=1, rate=16000,
                              input=True, frames_per_buffer=1024)
            stream.close()
            pya.terminate()
            results["microphone"] = True
        except Exception:
            pass

    return results


# ──────────────────────────────────────────────────────
#  Audio Pipeline: Mic → Gemini → Speaker
# ──────────────────────────────────────────────────────

async def listen_audio(pya, audio_queue_mic: asyncio.Queue, is_playing):
    """Capture mic audio. Sends silence while speaker is playing."""
    mic_info = pya.get_default_input_device_info()
    log("audio", f"Mic: {mic_info['name']}")

    audio_stream = await asyncio.to_thread(
        pya.open, format=FORMAT, channels=CHANNELS, rate=SEND_SAMPLE_RATE,
        input=True, input_device_index=int(mic_info["index"]),
        frames_per_buffer=CHUNK_SIZE,
    )

    SILENCE = b'\x00' * CHUNK_SIZE * 2

    try:
        while True:
            data = await asyncio.to_thread(
                audio_stream.read, CHUNK_SIZE, exception_on_overflow=False,
            )
            if is_playing.is_set():
                await audio_queue_mic.put({"data": SILENCE, "mime_type": "audio/pcm"})
            else:
                await audio_queue_mic.put({"data": data, "mime_type": "audio/pcm"})
    finally:
        audio_stream.close()


async def send_audio_to_gemini(session, audio_queue_mic: asyncio.Queue):
    """Stream mic audio to Gemini Live session."""
    while True:
        msg = await audio_queue_mic.get()
        await session.send_realtime_input(audio=msg)


async def play_audio(pya, audio_queue_output: asyncio.Queue, is_playing, bridge=None):
    """Play Gemini's audio response through speaker."""
    speaker_stream = await asyncio.to_thread(
        pya.open, format=FORMAT, channels=CHANNELS,
        rate=RECEIVE_SAMPLE_RATE, output=True,
    )
    try:
        while True:
            bytestream = await audio_queue_output.get()
            is_playing.set()
            await asyncio.to_thread(speaker_stream.write, bytestream)
            if audio_queue_output.empty():
                is_playing.clear()
                if bridge:
                    await bridge.send_status("listening")
    finally:
        is_playing.clear()
        speaker_stream.close()


async def receive_from_gemini(
    session,
    audio_queue_output: asyncio.Queue,
    action_queue: asyncio.Queue,
    api_key: str,
    task_running: asyncio.Event,
    bridge=None,
):
    """Receive audio + text + tool_calls from Gemini Live API.
    
    Per Google's official docs, the Live API emits:
      - response.server_content  → audio/text from the model
      - response.tool_call       → function call requests (NOT inside server_content)
    
    Tool responses must be sent back via session.send_tool_response().
    """
    while True:
        turn = session.receive()

        async for response in turn:
            # ── Handle audio and text from the model ──
            if response.server_content:
                model_turn = response.server_content.model_turn
                if model_turn and model_turn.parts:
                    for part in model_turn.parts:
                        if part.inline_data and isinstance(part.inline_data.data, bytes):
                            audio_queue_output.put_nowait(part.inline_data.data)
                        elif part.text:
                            text = part.text.strip()
                            if text:
                                log("companion", f"📝 {text[:120]}")
                                if bridge:
                                    await bridge.send_companion_message(text)

            # ── Handle tool calls (CORRECT Live API pattern) ──
            if response.tool_call:
                for fc in response.tool_call.function_calls:
                    func_name = fc.name
                    func_id = fc.id  # Must be passed back in FunctionResponse
                    args_dict = dict(fc.args) if fc.args else {}
                    
                    log("companion", f"🛠️ Tool call: {func_name} (id={func_id})")
                    
                    if func_name == "perform_computer_task":
                        task_goal = args_dict.get("goal", "")
                        if task_goal:
                            log("computer", f"🖥️  Delegating to Computer Agent: {task_goal[:80]}")
                            if bridge:
                                await bridge.send_status("acting", f"Working on: {task_goal[:40]}")
                                await bridge.send_activity(f"Computer task: {task_goal[:40]}", "🖥️")
                            await action_queue.put({
                                "name": func_name,
                                "id": func_id,
                                "goal": task_goal,
                            })
                    elif func_name == "remember_information":
                        fact = args_dict.get("fact", "")
                        log("system", f"🧠 Memory: Storing '{fact[:60]}'")
                        await action_queue.put({
                            "name": func_name,
                            "id": func_id,
                            "fact": fact,
                            "context": args_dict.get("context", "General"),
                        })
                    elif func_name == "read_memory":
                        query = args_dict.get("query", "")
                        log("system", f"🧠 Memory: Retrieving '{query[:60]}'")
                        await action_queue.put({
                            "name": func_name,
                            "id": func_id,
                            "query": query,
                        })
                    else:
                        # Unknown tool — return error immediately
                        log("error", f"Unknown tool call: {func_name}")
                        try:
                            await session.send_tool_response(
                                function_responses=[types.FunctionResponse(
                                    name=func_name,
                                    id=func_id,
                                    response={"error": f"Unknown tool: {func_name}"},
                                )]
                            )
                        except Exception as e:
                            logger.warning(f"Failed to send unknown-tool response: {e}")

        if bridge:
            await bridge.send_status("listening")


# ──────────────────────────────────────────────────────
#  Computer Use Worker — Executes Tasks in Background
# ──────────────────────────────────────────────────────

async def computer_use_worker(
    action_queue: asyncio.Queue,
    session,
    api_key: str,
    task_running: asyncio.Event,
    bridge=None,
):
    """Background worker: executes tool calls and sends results via send_tool_response."""
    from google.genai import types as genai_types
    from src.orchestrator.computer_agent import run_computer_task

    while True:
        action_data = await action_queue.get()
        func_name = action_data.get("name")
        func_id = action_data.get("id")  # Required by Live API
        task_running.set()

        try:
            result_payload = {}

            if func_name == "perform_computer_task":
                task = action_data.get("goal", "")
                log("computer", f"{C.MAGENTA}Starting computer task: {task[:60]}{C.RESET}")

                async def on_status(status):
                    log("computer", f"  {C.DIM}{status}{C.RESET}")
                    if bridge:
                        await bridge.send_activity(status, "⚡")

                async def on_action(name, args):
                    log("computer", f"  → {name}")
                    if bridge:
                        await bridge.send_activity(f"Action: {name}", "🎯")

                try:
                    result = await run_computer_task(
                        goal=task,
                        api_key=api_key,
                        on_status=on_status,
                        on_action=on_action,
                        memory_store=memory_store if "memory_store" in globals() else None,
                    )
                    log("computer", f"{C.GREEN}✓ Task done: {result[:80]}{C.RESET}")
                    if bridge:
                        await bridge.send_activity(f"Done: {result[:40]}", "✅", "success")
                    result_payload = {"result": result[:500]}
                except Exception as task_err:
                    error_msg = f"Computer task failed: {task_err}"
                    log("error", f"{C.RED}{error_msg}{C.RESET}")
                    if bridge:
                        await bridge.send_activity(f"Failed: {str(task_err)[:40]}", "❌", "error")
                    result_payload = {"error": error_msg[:500]}

            elif func_name == "remember_information":
                fact = action_data.get("fact", "")
                context_label = action_data.get("context", "General")
                log("system", f"{C.GREEN}✓ Remembering: {fact[:60]}{C.RESET}")
                
                # Save to Firestore and local memory
                if "firestore_db" in globals() and firestore_db:
                    try:
                        doc_ref = firestore_db.collection("companion_memory").document()
                        mem_data = {
                            "fact": fact,
                            "context": context_label,
                            "timestamp": firestore.SERVER_TIMESTAMP
                        }
                        await doc_ref.set(mem_data)
                        
                        # Add to local store for fast retrieval
                        if "memory_store" in globals():
                            memory_store.append({"fact": fact, "context": context_label})
                            
                        result_payload = {"status": "success", "message": f"Successfully committed to permanent memory: {fact}"}
                    except Exception as e:
                        logger.error(f"Firestore save error: {e}")
                        result_payload = {"status": "error", "message": f"Failed to save to memory: {e}"}
                else:
                    result_payload = {"status": "error", "message": "Memory system offline (Firestore not initialized)"}

            elif func_name == "read_memory":
                query = action_data.get("query", "").lower()
                log("system", f"🧠 Searching memory for: {query[:60]}")
                
                if "memory_store" not in globals() or not memory_store:
                    result_payload = {"status": "success", "results": "Memory vault is empty."}
                else:
                    # Simple keyword matching on the local memory store
                    keywords = [k.strip() for k in query.replace("?", "").split() if len(k) > 2]
                    
                    matches = []
                    for mem in memory_store:
                        fact_lower = mem.get("fact", "").lower()
                        # If any keyword matches, or if query is very broad
                        if not keywords or any(k in fact_lower for k in keywords) or query in fact_lower:
                            matches.append(mem.get("fact", ""))
                    
                    if matches:
                        # Return all matches joined as a list
                        result_payload = {"status": "success", "results": "Found the following memories:\n- " + "\n- ".join(matches)}
                    else:
                        result_payload = {"status": "success", "results": "No relevant memories found for this query."}

            else:
                result_payload = {"error": f"Unknown function: {func_name}"}

            # ── Send tool response back to Live API (CORRECT protocol) ──
            await session.send_tool_response(
                function_responses=[genai_types.FunctionResponse(
                    name=func_name,
                    id=func_id,
                    response=result_payload,
                )]
            )
            log("system", f"✓ Tool response sent for {func_name}")

        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
            log("error", f"{C.RED}✗ Worker error: {e}{C.RESET}")
            # Try to send error response so model doesn't hang
            try:
                await session.send_tool_response(
                    function_responses=[genai_types.FunctionResponse(
                        name=func_name,
                        id=func_id,
                        response={"error": str(e)[:500]},
                    )]
                )
            except Exception:
                logger.error("Failed to send error response to Live API")
        finally:
            task_running.clear()
            if bridge:
                await bridge.send_status("listening")


# ──────────────────────────────────────────────────────
#  Main Loop — Multi-Model Pipeline
# ──────────────────────────────────────────────────────

async def run_companion():
    """Main multi-model companion loop."""
    from google import genai
    from google.genai import types
    from src.orchestrator.voice_bridge import VoiceBridge
    from src.orchestrator.gemini.prompts_v2 import PERSONALITY_THEMES

    banner()

    if not HAS_PYAUDIO:
        print(f"\n{C.RED}  ERROR: pyaudio required. Run: brew install portaudio && pip install pyaudio{C.RESET}\n")
        return

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print(f"\n{C.RED}  ERROR: GEMINI_API_KEY not set.{C.RESET}\n")
        return

    client = genai.Client(
        api_key=api_key,
        http_options={"api_version": "v1alpha"},
    )
    
    # Initialize Firestore Memory System
    global firestore_db, memory_store
    firestore_db = None
    memory_store = []
    
    gcp_project = os.environ.get("GCP_PROJECT_ID")
    if gcp_project:
        try:
            log("system", "Connecting to Firestore Memory Vault...")
            firestore_db = firestore.AsyncClient(project=gcp_project)
            
            # Fetch existing memories
            memories_ref = firestore_db.collection("companion_memory").order_by("timestamp", direction=firestore.Query.ASCENDING)
            docs = await memories_ref.get()
            
            for doc in docs:
                data = doc.to_dict()
                if "fact" in data:
                    memory_store.append(data)
            
            log("system", f"{C.GREEN}✓ Loaded {len(memory_store)} memories from vault{C.RESET}")
        except Exception as e:
            log("error", f"{C.YELLOW}⚠ Could not initialize Firestore memory: {e}{C.RESET}")
    else:
        log("error", f"{C.YELLOW}⚠ GCP_PROJECT_ID not set. Memory will not be persisted.{C.RESET}")

    # Permissions
    log("system", "Checking macOS permissions...")
    permissions = await validate_permissions()
    for perm, ok in permissions.items():
        icon = f"{C.GREEN}✓" if ok else f"{C.YELLOW}⚠"
        log("system", f"{icon} {perm.replace('_', ' ').title()}{C.RESET}")

    if not permissions["microphone"]:
        print(f"\n{C.RED}  ERROR: Microphone access denied.{C.RESET}\n")
        return

    # UI bridge
    bridge = VoiceBridge()
    try:
        await bridge.start()
        log("system", f"{C.GREEN}UI bridge: ws://127.0.0.1:8765{C.RESET}")
    except Exception as e:
        log("system", f"{C.YELLOW}UI bridge unavailable: {e}{C.RESET}")
        bridge = None

    personality = "friendly"
    theme = PERSONALITY_THEMES[personality]

    # Map Tools for the Live Client
    tools = [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="perform_computer_task",
                    description="Perform a task on the user's computer screen by controlling the mouse and keyboard. Use this when the user asks you to interact with an application, browse the web, open a program, etc.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "goal": types.Schema(
                                type=types.Type.STRING,
                                description="The specific natural language goal to accomplish on the computer.",
                            ),
                        },
                        required=["goal"],
                    )
                ),
                types.FunctionDeclaration(
                    name="remember_information",
                    description="Store a fact, preference, or piece of information permanently in the user's memory vault.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "fact": types.Schema(type=types.Type.STRING, description="The specific fact to remember."),
                            "context": types.Schema(type=types.Type.STRING, description="The category or context (e.g. 'Work', 'Personal')."),
                        },
                        required=["fact"],
                    )
                ),
                types.FunctionDeclaration(
                    name="read_memory",
                    description="Retrieve a piece of information or context from the user's memory vault.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "query": types.Schema(type=types.Type.STRING, description="What to search for in memory."),
                        },
                        required=["query"],
                    )
                )
            ]
        )
    ]

    # Live API config with TOOLS
    base_system_instruction = (
        "IMPORTANT: Always speak in English regardless of what language the user uses. "
        "You are OmniCompanion, a powerful AI assistant that controls this Mac computer. "
        f"{theme['style']} "
        "You can do ANYTHING on this computer: open apps, browse the web, search for products, "
        "click, type, scroll, manage files, run commands, send messages, check email, play music, and more. "
        "CRITICAL EXECUTOR RULES:\n"
        "If the user asks you to perform an action on the computer, FIRST enthusiastically tell the user you are starting the task! "
        "Talk playfully about what you are going to do, and THEN immediately invoke the `perform_computer_task` tool. "
        "It is very important that you talk and reassure the user before going silent to execute the function."
    )
    
    memory_context = ""
    if "memory_store" in globals() and memory_store:
        memory_context = "\n\n--- YOUR MEMORY VAULT ---\nYou have previously remembered the following facts about the user:\n"
        for mem in memory_store:
            fact = mem.get("fact", "")
            context = mem.get("context", "General")
            memory_context += f"- [{context}] {fact}\n"
        memory_context += "Use these facts proactively to personalize your responses and actions.\n-------------------------"

    config = {
        "tools": tools,
        "response_modalities": ["AUDIO"],
        "speech_config": {
            "voice_config": {
                "prebuilt_voice_config": {"voice_name": "Charon"},
            },
        },
        "system_instruction": base_system_instruction + memory_context,
    }

    # Audio queues
    pya = pyaudio.PyAudio()
    audio_queue_output = asyncio.Queue()
    audio_queue_mic = asyncio.Queue(maxsize=5)
    is_playing = asyncio.Event()
    action_queue = asyncio.Queue()  # Queue for computer tasks
    task_running = asyncio.Event()  # Lock for tasks

    log("system", f"Actor model: Computer Use Preview")
    log("system", f"{C.GREEN}Connecting to Gemini Live with Function Calling...{C.RESET}")

    if bridge:
        await bridge.send_status("thinking", "Connecting...")
        await bridge.send_activity("Connecting to Gemini Live...", "🔌")

    # Try each model name until one connects
    connected_model = None
    session_ctx = None
    for model_name in LIVE_API_MODELS:
        log("system", f"Trying model: {model_name}...")
        try:
            session_ctx = client.aio.live.connect(
                model=model_name,
                config=config,
            )
            session = await session_ctx.__aenter__()
            connected_model = model_name
            log("system", f"{C.GREEN}{C.BOLD}✓ Connected to {model_name}!{C.RESET}")
            break
        except Exception as e:
            log("system", f"{C.YELLOW}✗ {model_name}: {str(e)[:80]}{C.RESET}")
            session_ctx = None
            continue

    if not connected_model or not session_ctx:
        log("error", f"{C.RED}All Live API models failed. Check your GEMINI_API_KEY and SDK version.{C.RESET}")
        log("error", f"{C.RED}Try: pip install --upgrade google-genai{C.RESET}")
        pya.terminate()
        if bridge:
            await bridge.stop()
        return

    try:
        print(f"\n  {C.CYAN}🎤 Microphone is live — just start talking!{C.RESET}")
        print(f"  {C.DIM}  Say things like 'Open Safari and go to Google'{C.RESET}")
        print(f"  {C.DIM}  Press Ctrl+C to stop{C.RESET}\n")

        if bridge:
            await bridge.send_status("listening", "Ready!")
            await bridge.send_activity(f"Connected to {connected_model}!", "✅", "success")

        async with asyncio.TaskGroup() as tg:
            tg.create_task(listen_audio(pya, audio_queue_mic, is_playing))
            tg.create_task(send_audio_to_gemini(session, audio_queue_mic))
            tg.create_task(receive_from_gemini(
                session, audio_queue_output, action_queue, api_key, task_running, bridge
            ))
            tg.create_task(play_audio(pya, audio_queue_output, is_playing, bridge))
            tg.create_task(computer_use_worker(
                action_queue, session, api_key, task_running, bridge
            ))

    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Session error: {e}", exc_info=True)
        log("error", f"{C.RED}Session error: {e}{C.RESET}")
    finally:
        pya.terminate()
        if bridge:
            await bridge.stop()
        print(f"\n{C.CYAN}  👋 OmniCompanion shut down. See you!{C.RESET}\n")


def main():
    try:
        asyncio.run(run_companion())
    except KeyboardInterrupt:
        print(f"\n{C.DIM}  Interrupted.{C.RESET}")


if __name__ == "__main__":
    main()
