# OmniCompanion — Demo Video Script

## Video Overview
- **Title:** OmniCompanion — Your AI Desktop Companion
- **Duration:** 3–4 minutes
- **Category:** UI Navigator ☸️
- **Format:** Screen recording with voice narration

---

## Scene 1: Introduction (0:00–0:30)

**Visual:** OmniCompanion PiP window appears on desktop, 3D avatar idle with breathing animation.

**Narration:**
> "Meet OmniCompanion — an AI-powered desktop companion that understands your screen, plans multi-step tasks, and executes them autonomously using Gemini 1.5 Pro."

**On-screen:** Title card with OmniCompanion logo, category badge "UI Navigator".

---

## Scene 2: Architecture Overview (0:30–1:00)

**Visual:** Animated diagram showing the 7-agent architecture.

**Narration:**
> "Under the hood, OmniCompanion runs a 7-agent orchestration pipeline:
> Executive Planner, UI Vision, Action Executor, Browser Automation,
> Memory, Verification, and Safety Monitor — all powered by Gemini."

**On-screen:** Architecture diagram from `docs/ARCHITECTURE.md`.

---

## Scene 3: Live Demo — Opening an App (1:00–2:00)

**Visual:** User says "Open Chrome and go to google.com"

**Steps shown:**
1. PiP avatar activates (blue → purple)
2. Execution log shows: `planner → Plan with 6 steps`
3. Vision agent highlights Chrome icon on dock (green bounding box)
4. Executor clicks Chrome icon (mouse animation)
5. Browser agent navigates to google.com
6. Verifier confirms: ✅ "Google loaded" (confidence: 94%)
7. Avatar returns to idle

**Narration:**
> "Watch as OmniCompanion breaks down the goal, identifies the Chrome icon
> using vision, clicks it, navigates to Google, and verifies success —
> all in under 10 seconds."

---

## Scene 4: Safety in Action (2:00–2:30)

**Visual:** User says "Delete all files in Downloads"

**Steps shown:**
1. Safety Monitor intercepts with red warning
2. Execution log: `safety → BLOCKED: Destructive operation`
3. PiP window shows confirmation dialog
4. User denies → action cancelled

**Narration:**
> "Safety is built in. The Safety Monitor uses hardcoded rules and
> Gemini-based risk assessment. Dangerous actions are always blocked
> or require explicit user confirmation."

---

## Scene 5: Memory & Learning (2:30–3:00)

**Visual:** Second "Open Chrome" request executes faster.

**Narration:**
> "OmniCompanion remembers. Short-term memory tracks actions within
> a session, while Firestore-backed long-term memory learns across
> sessions — making repeat tasks faster."

---

## Scene 6: Technical Highlights (3:00–3:30)

**Visual:** Code snippets and terminal output.

**Key points:**
- ✅ Gemini 1.5 Pro multimodal input (screenshots + text)
- ✅ Cross-platform Rust system layer (screen capture, input control)
- ✅ Electron PiP overlay with Three.js avatar
- ✅ 80/80 tests passing
- ✅ Terraform-based GCP deployment
- ✅ Token bucket rate limiting & structured audit logging

---

## Scene 7: Closing (3:30–3:45)

**Visual:** OmniCompanion avatar waves, title card.

**Narration:**
> "OmniCompanion: see your screen. Plan the path. Take the action.
> Built for the Gemini Live Agent Challenge."

---

## Production Notes

- **Recording tool:** OBS Studio or QuickTime
- **Resolution:** 1920×1080
- **Frame rate:** 60fps
- **Audio:** Clean voiceover, no background music
- **Captions:** Include subtitles for accessibility
