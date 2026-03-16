# OmniCompanion — Tech Stack

## Overview
Every dependency is pinned to a specific version. No deviations from this stack are permitted.

---

## Core Languages

| Language | Version | Purpose | Justification |
|----------|---------|---------|---------------|
| Python | 3.11 | Backend orchestrator, agents, Gemini client | Primary ML/AI ecosystem, Vertex AI SDK support |
| Rust | 1.75+ | System control layer | Memory-safe, native performance, cross-platform compilation |
| TypeScript | 5.x (strict) | Frontend UI shell | Type safety for React + Electron development |

---

## Backend (Python) Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `google-cloud-aiplatform` | >=1.38.0 | Vertex AI SDK — Gemini model access |
| `google-cloud-firestore` | >=2.13.0 | Firestore client for long-term memory |
| `google-cloud-storage` | >=2.14.0 | Cloud Storage client for media artifacts |
| `google-cloud-logging` | >=3.8.0 | Cloud Logging client for audit trail |
| `grpcio` | >=1.60.0 | gRPC Python runtime |
| `grpcio-tools` | >=1.60.0 | Protobuf code generation |
| `protobuf` | >=4.25.0 | Protobuf Python runtime |
| `playwright` | >=1.40.0 | Browser automation |
| `pytesseract` | >=0.3.10 | OCR engine wrapper |
| `Pillow` | >=10.0.0 | Image processing |
| `aiohttp` | >=3.9.0 | Async HTTP client |
| `pydantic` | >=2.5.0 | Data validation + serialization |
| `python-dotenv` | >=1.0.0 | Environment variable management |
| `structlog` | >=23.2.0 | Structured logging |
| `tenacity` | >=8.2.0 | Retry logic with exponential backoff |
| `pytest` | >=7.4.0 | Unit testing |
| `pytest-asyncio` | >=0.23.0 | Async test support |

---

## System Layer (Rust) Dependencies

| Crate | Version | Purpose |
|-------|---------|---------|
| `tonic` | 0.11 | gRPC server framework |
| `prost` | 0.12 | Protobuf code generation |
| `tokio` | 1.35 | Async runtime |
| `image` | 0.24 | Image encoding (PNG) |
| `core-graphics` | 0.23 | macOS screen capture |
| `core-foundation` | 0.9 | macOS Core Foundation bindings |
| `windows` | 0.52 | Windows API bindings |
| `x11rb` | 0.13 | X11 protocol bindings (Linux) |
| `enigo` | 0.2 | Cross-platform input simulation |
| `tracing` | 0.1 | Structured logging |
| `serde` | 1.0 | Serialization |
| `serde_json` | 1.0 | JSON serialization |
| `anyhow` | 1.0 | Error handling |

---

## Frontend (Electron + React) Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `electron` | >=28.0.0 | Desktop shell |
| `react` | >=18.2.0 | UI framework |
| `react-dom` | >=18.2.0 | React DOM renderer |
| `three` | >=0.160.0 | WebGL 3D rendering (avatar) |
| `@react-three/fiber` | >=8.15.0 | React Three.js bindings |
| `@react-three/drei` | >=9.92.0 | Three.js helpers |
| `typescript` | >=5.3.0 | Type checking |
| `vite` | >=5.0.0 | Build tool |
| `electron-builder` | >=24.0.0 | Electron packaging |

---

## Infrastructure & DevOps

| Tool | Version | Purpose |
|------|---------|---------|
| Terraform | >=1.6.0 | GCP infrastructure-as-code |
| Docker | >=24.0 | Container builds |
| Tesseract | 5.x | OCR engine (system install) |
| protoc | 3.x | Protobuf compiler |
| gcloud CLI | latest | GCP authentication + deployment |

---

## External Services

| Service | Provider | Purpose |
|---------|----------|---------|
| Gemini 1.5 Pro | Google (Vertex AI) | Multimodal AI reasoning |
| Vertex AI Embeddings | Google (Vertex AI) | Semantic search for memory |
| Cloud Run | Google Cloud | Backend hosting |
| Firestore | Google Cloud | Document database |
| Cloud Storage | Google Cloud | Object storage |
| Cloud Logging | Google Cloud | Audit logging |
