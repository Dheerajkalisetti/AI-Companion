# OmniCompanion — System Architecture

## 1. High-Level Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                           OmniCompanion Architecture                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ┌────────────────────── PRESENTATION LAYER ──────────────────────┐          ║
║  │                                                                 │          ║
║  │  ┌─────────────────────────────────────────────────────────┐   │          ║
║  │  │              Electron Shell (TypeScript)                 │   │          ║
║  │  │  ┌──────────┐ ┌────────────┐ ┌──────────┐ ┌──────────┐ │   │          ║
║  │  │  │ Avatar   │ │ PiP Window │ │ Task     │ │Exec Log  │ │   │          ║
║  │  │  │ (WebGL/  │ │ (Always-   │ │ Progress │ │(Real-    │ │   │          ║
║  │  │  │ Three.js)│ │  on-top)   │ │ Display  │ │ time)    │ │   │          ║
║  │  │  └──────────┘ └────────────┘ └──────────┘ └──────────┘ │   │          ║
║  │  └───────────────────────┬─────────────────────────────────┘   │          ║
║  │                          │ IPC (Electron ↔ Node)               │          ║
║  └──────────────────────────┼─────────────────────────────────────┘          ║
║                             │                                                 ║
║  ┌──────────────────────────▼──── ORCHESTRATION LAYER ────────────┐          ║
║  │                     Python 3.11 Backend                         │          ║
║  │                                                                 │          ║
║  │  ┌────────────────── AGENT SYSTEM ───────────────────────────┐ │          ║
║  │  │                                                            │ │          ║
║  │  │  ┌──────────────┐    ┌──────────────┐                     │ │          ║
║  │  │  │  Executive    │───▶│  UI Vision   │                     │ │          ║
║  │  │  │  Planner (1)  │    │  Agent (2)   │                     │ │          ║
║  │  │  └──────┬───────┘    └──────┬───────┘                     │ │          ║
║  │  │         │                    │                              │ │          ║
║  │  │         ▼                    ▼                              │ │          ║
║  │  │  ┌──────────────┐    ┌──────────────┐  ┌──────────────┐  │ │          ║
║  │  │  │  Action       │    │  Browser     │  │  Memory      │  │ │          ║
║  │  │  │  Executor (3) │    │  Agent (4)   │  │  Agent (5)   │  │ │          ║
║  │  │  └──────┬───────┘    └──────┬───────┘  └──────┬───────┘  │ │          ║
║  │  │         │                    │                  │          │ │          ║
║  │  │         ▼                    ▼                  ▼          │ │          ║
║  │  │  ┌──────────────┐    ┌──────────────┐                     │ │          ║
║  │  │  │ Verification │    │  Safety      │                     │ │          ║
║  │  │  │ Agent (6)    │    │  Monitor (7) │                     │ │          ║
║  │  │  └──────────────┘    └──────────────┘                     │ │          ║
║  │  └────────────────────────────────────────────────────────────┘ │          ║
║  │                                                                 │          ║
║  │  ┌────────── GEMINI CLIENT ──────────┐  ┌── MEMORY LAYER ──┐  │          ║
║  │  │  Vertex AI SDK                     │  │  Short-Term (RAM)│  │          ║
║  │  │  • Text + Image → Response         │  │  Long-Term (DB)  │  │          ║
║  │  │  • Streaming                       │  │  Embeddings      │  │          ║
║  │  │  • Retry + Backoff                 │  └─────────┬────────┘  │          ║
║  │  └──────────────┬────────────────────┘             │           │          ║
║  │                 │                                   │           │          ║
║  │  ┌──────────────▼──── gRPC SERVER ─────────────────┼─────────┐ │          ║
║  │  │  Serves: OrchestratorService                    │         │ │          ║
║  │  │  Proto: orchestrator.proto                      │         │ │          ║
║  │  └──────────────┬──────────────────────────────────┼─────────┘ │          ║
║  └─────────────────┼──────────────────────────────────┼───────────┘          ║
║                    │ gRPC                              │                      ║
║  ┌─────────────────▼──── SYSTEM LAYER ────────────────┼───────────┐          ║
║  │                Rust 1.75+ Binary                    │           │          ║
║  │                                                     │           │          ║
║  │  ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │           │          ║
║  │  │  Screen      │ │  Input       │ │  Window    │ │           │          ║
║  │  │  Capture     │ │  Control     │ │  Manager   │ │           │          ║
║  │  │  (capture.rs)│ │  (input.rs)  │ │(window.rs) │ │           │          ║
║  │  └──────┬───────┘ └──────┬───────┘ └─────┬──────┘ │           │          ║
║  │         │                │                │        │           │          ║
║  │  ┌──────▼────────────────▼────────────────▼──────┐ │           │          ║
║  │  │           Platform Abstraction                 │ │           │          ║
║  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐      │ │           │          ║
║  │  │  │ Windows  │ │  macOS   │ │  Linux   │      │ │           │          ║
║  │  │  └──────────┘ └──────────┘ └──────────┘      │ │           │          ║
║  │  └────────────────────────────────────────────────┘ │           │          ║
║  └─────────────────────────────────────────────────────┼───────────┘          ║
║                                                        │                      ║
║  ┌──────────────────── EXTERNAL SERVICES ──────────────▼───────────┐          ║
║  │                                                                  │          ║
║  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ │          ║
║  │  │ Vertex   │ │ Cloud    │ │Firestore │ │ Cloud  │ │ Cloud  │ │          ║
║  │  │ AI       │ │ Run      │ │          │ │Storage │ │Logging │ │          ║
║  │  │(Gemini)  │ │(Backend) │ │(Memory)  │ │(Media) │ │(Audit) │ │          ║
║  │  └──────────┘ └──────────┘ └──────────┘ └────────┘ └────────┘ │          ║
║  └──────────────────────────────────────────────────────────────────┘          ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## 2. Component Descriptions

### 2.1 Presentation Layer — Electron Shell
The desktop UI built with Electron + React + TypeScript. Provides:
- **PiP Window**: Always-on-top draggable/resizable overlay showing the AI companion
- **Avatar**: WebGL 2.5D character rendered via Three.js with idle, active, and speaking animation states
- **Task Progress**: Visual representation of current task plan execution
- **Execution Log**: Real-time scrolling display of agent actions and decisions
- **Voice Indicator**: Waveform visualization during speech input/output

IPC communication with the Python backend via Electron's IPC bridge (stdin/stdout JSON messages).

### 2.2 Orchestration Layer — Python Backend
The central intelligence hub. Responsibilities:
- **Agent Coordination**: Routes tasks to appropriate agents based on the execution plan
- **Gemini Client**: Wraps Vertex AI SDK for all model calls (text, multimodal, streaming)
- **Memory Management**: Manages short-term (in-memory) and long-term (Firestore) context
- **gRPC Server**: Exposes `OrchestratorService` for the Rust system layer
- **Task Pipeline**: Implements the full perceive → plan → act → verify loop

### 2.3 System Layer — Rust Binary
Native system control compiled per-platform. Provides:
- **Screen Capture**: OS-native screenshot capture (CoreGraphics on macOS, Win32 API on Windows, X11/Wayland on Linux)
- **Input Control**: Programmatic mouse clicks, keyboard input, scrolling
- **Window Management**: Window enumeration, focus switching, position queries

Exposed via gRPC server using protobuf schemas defined in `src/proto/system.proto`.

### 2.4 External Services — Google Cloud Platform
- **Vertex AI**: Primary endpoint for Gemini 1.5 Pro model inference and embeddings
- **Cloud Run**: Hosts the Python orchestrator for cloud deployment
- **Firestore**: Document database for persistent memory, task history, and user preferences
- **Cloud Storage**: Binary object storage for screenshots, artifacts, and media
- **Cloud Logging**: Centralized audit logging for all agent actions

---

## 3. Data Flow

### 3.1 Task Execution Flow
```
User Input → Safety Monitor → Executive Planner → Task Plan
     │
     ▼
For each task step:
     │
     ├─→ UI Vision Agent ─→ Screen Analysis ─→ UI Element Map
     │
     ├─→ Action Executor Agent ─→ gRPC ─→ Rust System Layer ─→ OS Action
     │   OR
     ├─→ Browser Agent ─→ Playwright ─→ Browser Action
     │
     ├─→ Verification Agent ─→ Post-Action Screenshot ─→ Confirmation
     │
     └─→ Memory Agent ─→ Store Result ─→ Firestore
```

### 3.2 Gemini API Call Flow
```
Agent Request → Prompt Assembly → Multimodal Formatter
     │                                    │
     │         ┌──────────────────────────┘
     ▼         ▼
  Vertex AI SDK (google-cloud-aiplatform)
     │
     ├─→ Token Count Check (context window limit)
     ├─→ Safety Config (harm thresholds)
     ├─→ API Call (with retry + exponential backoff)
     │
     ▼
  Response → Parse JSON → Validate Schema → Return to Agent
```

---

## 4. Communication Protocols

| Path | Protocol | Format |
|------|----------|--------|
| Electron ↔ Python | IPC (stdin/stdout) | JSON messages |
| Python ↔ Rust | gRPC | Protobuf (system.proto) |
| Python ↔ Vertex AI | HTTPS | Vertex AI SDK |
| Python ↔ Firestore | HTTPS | Firestore SDK |
| Python ↔ Playwright | In-process | Python API |

---

## 5. Security Architecture

See `/docs/SECURITY_MODEL.md` for full threat model. Key points:
- No credentials in source code — `.env` files + GCP IAM
- Safety Monitor agent gates all destructive actions
- Rate limiting on Gemini API calls
- Audit logging to Cloud Logging for every agent action
- Input sanitization on all user-provided data
