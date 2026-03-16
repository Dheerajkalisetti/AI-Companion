# OmniCompanion — Agent Orchestration

## Overview
OmniCompanion uses a **7-agent multi-agent architecture** where each agent has a specialized role, defined I/O contracts, and specific tool access. The Executive Planner coordinates all other agents through a central orchestration loop.

---

## Orchestration Flow

```
User Goal (natural language)
        │
        ▼
┌───────────────────┐
│  Safety Monitor   │──── BLOCKED? ──→ Require user confirmation
│  Agent (7)        │
└───────┬───────────┘
        │ APPROVED
        ▼
┌───────────────────┐
│ Executive Planner │──→ Task Plan JSON
│  Agent (1)        │    {tasks: [{id, description, agent, tools, deps}]}
└───────┬───────────┘
        │
        ▼
┌─── FOR EACH TASK STEP ─────────────────────────────────────────┐
│                                                                 │
│   ┌───────────────────┐                                        │
│   │  UI Vision Agent  │──→ UI Element Map JSON                 │
│   │  (2)              │    {elements: [{type, label, bbox}]}   │
│   └───────┬───────────┘                                        │
│           │                                                     │
│           ▼                                                     │
│   ┌───────────────────┐    ┌───────────────────┐               │
│   │ Action Executor   │ OR │ Browser Agent     │               │
│   │ Agent (3)         │    │ (4)               │               │
│   │ → OS-level action │    │ → Web automation  │               │
│   └───────┬───────────┘    └───────┬───────────┘               │
│           │                        │                            │
│           └────────┬───────────────┘                            │
│                    ▼                                            │
│   ┌───────────────────┐                                        │
│   │ Verification      │──→ {verified: bool, confidence: 0.0-1.0}│
│   │ Agent (6)         │                                        │
│   └───────┬───────────┘                                        │
│           │                                                     │
│           ▼                                                     │
│   ┌───────────────────┐                                        │
│   │ Memory Agent (5)  │──→ Store task result in Firestore      │
│   └───────────────────┘                                        │
│                                                                 │
│   If verification fails (confidence < 0.85):                   │
│   → Re-plan step with Executive Planner                        │
│   → Retry up to 3 times                                        │
│   → If still failing, escalate to user                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Agent Specifications

### Agent 1: Executive Planner

| Property | Value |
|----------|-------|
| **File** | `src/orchestrator/agents/planner.py` |
| **Responsibility** | Receives user goal → decomposes into ordered task list |
| **Input** | Natural language goal string |
| **Output** | `{tasks: [{id, description, agent, tools, dependencies}]}` |
| **Gemini Prompt** | System prompt for task decomposition + structured JSON output |
| **Tools** | Gemini reasoning, Memory Agent read |
| **Verification** | Task plan parsed and validated against JSON schema |

**Behavior:**
1. Receives user goal as plain text
2. Queries Memory Agent for relevant context (past similar tasks)
3. Sends goal + context to Gemini with decomposition prompt
4. Parses response into validated task plan JSON
5. Returns ordered task list with dependencies

---

### Agent 2: UI Vision

| Property | Value |
|----------|-------|
| **File** | `src/orchestrator/agents/vision.py` |
| **Responsibility** | Analyzes screenshots → identifies UI elements, clickable targets, text |
| **Input** | PNG screenshot bytes + optional context string |
| **Output** | `{elements: [{type, label, bbox, confidence}]}` |
| **Gemini Prompt** | Multimodal prompt: screenshot image + "identify all interactive elements" |
| **Tools** | Gemini multimodal, OCR engine (Tesseract), Screen Capture |
| **Verification** | UI map contains at least 1 element; bbox coordinates within image dimensions |

**Behavior:**
1. Receives screenshot as PNG bytes
2. Runs OCR (Tesseract) for text extraction
3. Sends screenshot + OCR text + context to Gemini multimodal
4. Gemini identifies UI elements with types and bounding boxes
5. Parses response into validated UI map JSON
6. Merges OCR text regions with Gemini-detected elements

---

### Agent 3: Action Executor

| Property | Value |
|----------|-------|
| **File** | `src/orchestrator/agents/executor.py` |
| **Responsibility** | Translates action commands into OS-level inputs |
| **Input** | `{type: click|type|scroll|key, target: {x, y}|string, value: string|null}` |
| **Output** | `{success: bool, error: str|null, screenshot_after: bytes}` |
| **Tools** | Rust system layer via gRPC |
| **Verification** | Post-action screenshot compared to pre-action |

**Behavior:**
1. Receives action command JSON
2. Safety Monitor validates the action (if not already done at plan level)
3. Takes pre-action screenshot via Rust layer
4. Sends action command to Rust gRPC server
5. Rust layer executes OS-level input (mouse click, keyboard type, etc.)
6. Takes post-action screenshot
7. Returns result with post-action screenshot

---

### Agent 4: Browser Automation

| Property | Value |
|----------|-------|
| **File** | `src/orchestrator/agents/browser.py` |
| **Responsibility** | Web-specific automation via Playwright |
| **Input** | `{action: navigate|click|type|screenshot|dom, selector: str, url: str, value: str}` |
| **Output** | `{url: str, title: str, screenshot: bytes, dom_snapshot: str}` |
| **Tools** | Playwright Python |
| **Verification** | URL and title match expected post-action state |

**Behavior:**
1. Manages Playwright browser instance (launch/close lifecycle)
2. Receives browser action command
3. Executes action (navigate, click, type, extract DOM, screenshot)
4. Returns current browser state with screenshot and DOM snapshot
5. Handles Playwright-specific errors (element not found, timeout, etc.)

---

### Agent 5: Memory

| Property | Value |
|----------|-------|
| **File** | `src/orchestrator/agents/memory.py` |
| **Responsibility** | Store/retrieve short-term and long-term context |
| **Input** | `{op: read|write|search, key: str, data: any, query: str}` |
| **Output** | `{found: bool, data: any, relevance_score: float}` |
| **Tools** | Firestore client, Vertex AI Embeddings |
| **Verification** | Write confirmed by subsequent read |

**Behavior:**
1. **Read**: Exact key lookup in short-term (dict) then long-term (Firestore)
2. **Write**: Store data with key, generate embedding for semantic search
3. **Search**: Semantic search via Vertex AI Embeddings with cosine similarity
4. Scoring: `score = 0.7 * semantic_relevance + 0.3 * recency_weight`

---

### Agent 6: Verification

| Property | Value |
|----------|-------|
| **File** | `src/orchestrator/agents/verifier.py` |
| **Responsibility** | Secondary reasoning pass — confirms task completion |
| **Input** | Task definition + current screen state (screenshot) + execution log |
| **Output** | `{verified: bool, confidence: float, issues: [str]}` |
| **Gemini Prompt** | Multimodal: "Given this task X and the current screen, is the task complete?" |
| **Tools** | Gemini multimodal (separate prompt pass from planning) |
| **Verification** | Must achieve confidence > 0.85 to mark task step as complete |

**Behavior:**
1. Receives task description + post-action screenshot + execution log
2. Sends multimodal request to Gemini (separate from planning call)
3. Gemini evaluates whether the visible state matches expected outcome
4. Returns confidence score and list of issues if any
5. If confidence < 0.85, triggers re-planning

---

### Agent 7: Safety Monitor

| Property | Value |
|----------|-------|
| **File** | `src/orchestrator/agents/safety.py` |
| **Responsibility** | Risk classification before any destructive action |
| **Input** | Proposed action JSON |
| **Output** | `{approved: bool, risk_level: low|medium|high|critical, reason: str}` |
| **Tools** | Gemini safety prompting, hardcoded rule engine |
| **Verification** | All `high` and `critical` risk actions blocked without explicit user confirmation |

**Behavior:**
1. Receives proposed action before execution
2. Checks against hardcoded rule engine first (fast path):
   - File deletion → HIGH
   - System settings modification → CRITICAL
   - Network requests to unknown domains → MEDIUM
   - Read-only operations → LOW
3. If not matched by rules, sends to Gemini for risk assessment
4. Returns decision with risk level and reasoning
5. HIGH/CRITICAL actions require explicit user confirmation

---

## Error Recovery Strategy

When a task step fails:

```
Step fails → Increment retry counter
    │
    ├─ retry_count < 3:
    │   ├─ Take fresh screenshot
    │   ├─ Re-analyze with Vision Agent
    │   ├─ Executive Planner generates alternative approach
    │   └─ Execute alternative → Verify again
    │
    └─ retry_count >= 3:
        ├─ Log failure with full context
        ├─ Notify user via UI
        └─ Skip step or abort (user decides)
```
