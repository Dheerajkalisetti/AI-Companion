# OmniCompanion — Cloud Deployment Architecture

## GCP Topology

```
┌─────────────────────── Google Cloud Platform ──────────────────────┐
│                                                                     │
│  ┌─── Vertex AI ──────────────────────────────────────────────┐    │
│  │  • Gemini 1.5 Pro endpoint                                  │    │
│  │  • Text Embedding Model                                     │    │
│  │  • Region: us-central1                                      │    │
│  └───────────────────────────────┬─────────────────────────────┘    │
│                                  │                                   │
│  ┌─── Cloud Run ─────────────────▼────────────────────────────┐    │
│  │  Service: omnicompanion-orchestrator                        │    │
│  │  • Python 3.11 container                                    │    │
│  │  • Min instances: 1 (always warm)                           │    │
│  │  • Max instances: 10                                        │    │
│  │  • Memory: 2Gi                                              │    │
│  │  • CPU: 2                                                   │    │
│  │  • Concurrency: 1 (1 user = 1 instance)                    │    │
│  │  • Timeout: 300s                                            │    │
│  └──────┬──────────────────────────────────────────────────────┘    │
│         │                                                           │
│  ┌──────▼─── Firestore ───────────────────────────────────────┐    │
│  │  Database: omnicompanion-db                                 │    │
│  │  Mode: Native                                               │    │
│  │  Region: us-central1 (multi-region nam5)                    │    │
│  │                                                              │    │
│  │  Collections:                                                │    │
│  │  ├── sessions/{session_id}/tasks/{task_id}                  │    │
│  │  ├── user_preferences/{user_id}                             │    │
│  │  └── knowledge_base/{doc_id}                                │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─── Cloud Storage ──────────────────────────────────────────┐    │
│  │  Bucket: omnicompanion-artifacts                            │    │
│  │  Region: us-central1                                        │    │
│  │  Storage class: Standard                                    │    │
│  │                                                              │    │
│  │  Structure:                                                  │    │
│  │  ├── screenshots/{session_id}/{timestamp}.png               │    │
│  │  ├── dom_snapshots/{session_id}/{timestamp}.html            │    │
│  │  └── exports/{session_id}/                                  │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─── Cloud Logging ──────────────────────────────────────────┐    │
│  │  Log name: omnicompanion-audit                              │    │
│  │  Retention: 30 days                                         │    │
│  │                                                              │    │
│  │  Log structure:                                              │    │
│  │  {timestamp, phase, agent, action, input_summary,           │    │
│  │   output_summary, duration_ms, success}                     │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─── IAM & Security ─────────────────────────────────────────┐    │
│  │  Service Account: omnicompanion-sa@{project}.iam            │    │
│  │  Roles:                                                     │    │
│  │  ├── roles/aiplatform.user (Vertex AI)                      │    │
│  │  ├── roles/datastore.user (Firestore)                       │    │
│  │  ├── roles/storage.objectAdmin (GCS)                        │    │
│  │  ├── roles/logging.logWriter (Cloud Logging)                │    │
│  │  └── roles/run.invoker (Cloud Run)                          │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Local vs Cloud Boundary

| Component | Local Development | Cloud Production |
|-----------|------------------|------------------|
| Python Orchestrator | `python main.py` (localhost) | Cloud Run container |
| Rust System Layer | Local binary | Local binary (always local — needs OS access) |
| Electron UI | `npm run dev` (localhost) | Packaged Electron app |
| Firestore | Firestore emulator | Cloud Firestore |
| Gemini | Vertex AI (real API) | Vertex AI (real API) |
| Cloud Storage | Local filesystem fallback | GCS bucket |
| Cloud Logging | Console/file logging | Cloud Logging API |

**Key Insight:** The Rust system layer **always runs locally** — it needs direct OS access for screen capture and input control. Cloud Run hosts only the Python orchestrator. In local dev, the orchestrator and Rust layer run on the same machine.

---

## Environment Variables

| Variable | Description | Required |
|----------|-----------|----------|
| `GCP_PROJECT_ID` | Google Cloud project ID | Yes |
| `GCP_REGION` | GCP region (default: us-central1) | Yes |
| `GCP_SERVICE_ACCOUNT_KEY` | Path to service account JSON key | Local only |
| `VERTEX_AI_LOCATION` | Vertex AI region | Yes |
| `FIRESTORE_DATABASE` | Firestore database name | Yes |
| `GCS_BUCKET` | Cloud Storage bucket name | Yes |
| `CLOUD_LOGGING_LOG_NAME` | Cloud Logging log name | Yes |
| `GRPC_PORT` | gRPC server port (default: 50051) | No |
| `ORCHESTRATOR_PORT` | Orchestrator HTTP port (default: 8080) | No |
| `ENVIRONMENT` | `local` or `production` | Yes |

---

## Deployment Flow

```
Developer Machine                    Google Cloud
─────────────────                    ────────────
1. Code changes
2. docker build                 ──→  3. Push to Artifact Registry
                                      4. Deploy to Cloud Run
                                      5. Cloud Run pulls container
                                      6. Service starts with env vars
                                      7. Health check passes
                                      8. Traffic routed
```
