# OmniCompanion — Tool Usage Matrix

## Agent × Tool Access Matrix

| Tool | 1. Planner | 2. Vision | 3. Executor | 4. Browser | 5. Memory | 6. Verifier | 7. Safety |
|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Gemini Text Generation | ✅ | — | — | — | — | — | ✅ |
| Gemini Multimodal (Image+Text) | — | ✅ | — | — | — | ✅ | — |
| Gemini Embeddings | — | — | — | — | ✅ | — | — |
| OCR (Tesseract) | — | ✅ | — | — | — | — | — |
| Screen Capture (Rust) | — | ✅ | ✅ | — | — | ✅ | — |
| Mouse/Keyboard (Rust) | — | — | ✅ | — | — | — | — |
| Window Management (Rust) | — | — | ✅ | — | — | — | — |
| Playwright Browser | — | — | — | ✅ | — | — | — |
| Firestore Read | ✅ | — | — | — | ✅ | — | — |
| Firestore Write | — | — | — | — | ✅ | — | — |
| Cloud Storage | — | — | — | — | ✅ | — | — |
| Cloud Logging | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Safety Rule Engine | — | — | — | — | — | — | ✅ |
| Memory Agent (delegated) | ✅ | — | — | — | — | — | — |

---

## Tool Descriptions

### Gemini Tools
| Tool | Description | Access Pattern |
|------|-----------|----------------|
| Text Generation | Send text prompt → receive text response | Vertex AI SDK `generate_content()` |
| Multimodal | Send image + text → receive text response | Vertex AI SDK `generate_content()` with image Part |
| Embeddings | Generate vector embedding for text | Vertex AI SDK `TextEmbeddingModel` |

### System Tools (Rust via gRPC)
| Tool | Description | gRPC Method |
|------|-----------|-------------|
| Screen Capture | Capture screenshot as PNG bytes | `SystemService.CaptureScreen` |
| Mouse/Keyboard | Execute OS-level input actions | `SystemService.ExecuteAction` |
| Window Management | List/focus/query windows | `SystemService.ManageWindow` |

### Browser Tools
| Tool | Description | Playwright API |
|------|-----------|---------------|
| Navigate | Go to URL | `page.goto(url)` |
| Click | Click element by selector | `page.click(selector)` |
| Type | Type text into element | `page.fill(selector, value)` |
| Screenshot | Capture browser screenshot | `page.screenshot()` |
| DOM Snapshot | Extract page DOM | `page.content()` |

### Data Tools
| Tool | Description | SDK |
|------|-----------|-----|
| Firestore Read | Query documents by key or filter | `google-cloud-firestore` |
| Firestore Write | Create/update documents | `google-cloud-firestore` |
| Cloud Storage | Upload/download binary objects | `google-cloud-storage` |
| Cloud Logging | Write structured log entries | `google-cloud-logging` |

### Safety Tools
| Tool | Description | Implementation |
|------|-----------|----------------|
| Safety Rule Engine | Hardcoded risk classification rules | Python dict-based rule matching |

---

## Access Control Rules

1. **No agent can access tools outside its row** — enforced at the orchestrator level
2. **Cloud Logging is universal** — every agent logs every action
3. **Safety Monitor runs BEFORE Action Executor and Browser Agent** — no action proceeds without safety clearance
4. **Memory Agent is the ONLY writer to Firestore** — other agents request via the Memory Agent
5. **Planner reads memory via Memory Agent delegation** — does not access Firestore directly
