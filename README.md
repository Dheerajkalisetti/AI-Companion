# OmniCompanion v2 🗣️🖱️
**Your native macOS AI Desktop Companion — Powered by Gemini Live & 2.5 Flash**

> 🏆 Built for the **Gemini Live Agent Challenge** | Category: **Live Agents 🗣️ & UI Navigator ☸️**

---

## What is OmniCompanion?

OmniCompanion breaks the AI out of the browser tab. It is an autonomous, voice-driven desktop companion that **listens to your voice, sees your screen, and natively controls your mouse and keyboard.**

Don't type. Just speak.

```text
"Open WhatsApp and send a message to David."
→ Voice Model: Transcribes and extracts intent
→ Planner Model: Analyzes your screen and plots exact coordinates
→ Executor: Natively opens WhatsApp, clicks the search bar, types, and sends.
```

---

## The "Planner-First" Architecture

Traditional "Computer Use" models operate synchronously: they take a screenshot, make one mouse move, take another screenshot, click, etc. This takes 10-30 API calls for a single task, running into extreme rate limits and latency.

OmniCompanion uses a **Planner-First Multi-Model Architecture**:

1. **Voice (Gemini Live API):** Streams bidirectional audio for seamless conversation.
2. **Planner (`gemini-2.5-flash`):** Takes a single screenshot and the user's goal, and outputs a JSON array containing *every single step* required.
3. **OS Executor (PyAutoGUI / Subprocess):** Executes the entire JSON array natively on macOS. 
4. **Memory Vault (Google Cloud Firestore):** Stores long-term memory so the agent remembers user preferences across sessions.

*Result: Complex desktop tasks completed in exactly 2 API calls with zero rate limiting.*

---

## Technologies Used

* **Google GenAI SDK**
* **Gemini 2.5 Flash Native Audio Preview** (Bi-directional Voice)
* **Gemini 2.5 Flash** (Vision & Spatial Planning)
* **Google Cloud Firestore** (Persistent Memory)
* **PyAutoGUI** (Mouse/Keyboard Control)
* **Electron & Vite** (Floating Dashboard UI)

---

## Quick Start (Judge Reproducibility Guide)

OmniCompanion runs natively on **macOS** (pyaudio and pyautogui dependency).

### 1. Prerequisites
Ensure you have Python 3.11+, Node.js, and system audio headers installed:
```bash
brew install portaudio
```

### 2. Setup
Clone the repository and install the backend/frontend dependencies.
```bash
git clone <your-repo> && cd AI-Companion
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd src/ui && npm install && cd ../..
```

### 3. Google Cloud configuration
Copy the env file and add your keys:
```bash
cp .env.example .env
```
Inside `.env`, ensure the following are set:
* `GEMINI_API_KEY`: Your Gemini API Key from Google AI Studio.
* `GCP_PROJECT_ID`: A Google Cloud Project ID with **Firestore** initialized in Native Mode.
* `GOOGLE_APPLICATION_CREDENTIALS`: Path to your GCP service account JSON key (required for Firestore access).

### 4. Run the App
Start both the Python orchestrator and the Electron UI with one command:
```bash
./start_v2.sh
```

**Wait for the "Microphone is live" message in the terminal.** 
The floating UI will appear. You do not need to push a button. Just talk to your computer! 

*Try saying:*
* "What is on my screen right now?"
* "Open Google Chrome and go to wikipedia.org."
* "Remember that my favourite programming language is Python." (This will save to Firestore!)
* "Create a folder on my desktop called 'Hackathon' using the terminal."

---

## Verification of Cloud Usage
This project utilizes **Google Cloud Firestore** for persistent memory.
* See `src/orchestrator/companion_v2.py` (line 400+) for Firestore initialization.
* See `src/orchestrator/companion_v2.py` (`remember_information` tool) for dynamic document creation using the `google-cloud-firestore` SDK.

---

*Built for the Gemini Live Agent Challenge 2024.*
