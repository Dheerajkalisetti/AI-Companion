# OmniCompanion — Deployment Guide

## Prerequisites

1. **Google Cloud SDK** — [Install](https://cloud.google.com/sdk/docs/install)
2. **Terraform** >= 1.6.0 — [Install](https://developer.hashicorp.com/terraform/install)
3. **Docker** >= 24.0 — [Install](https://docs.docker.com/get-docker/)
4. **Python** 3.11+ — [Install](https://www.python.org/downloads/)
5. **Rust** 1.75+ — [Install](https://rustup.rs/)
6. **Node.js** 18+ — [Install](https://nodejs.org/)

---

## Step 1: GCP Project Setup

```bash
# Authenticate with Google Cloud
gcloud auth login
gcloud auth application-default login

# Set project
gcloud config set project YOUR_PROJECT_ID

# Enable billing (required for Vertex AI)
# Visit: https://console.cloud.google.com/billing
```

---

## Step 2: Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your values
# At minimum, set:
#   GCP_PROJECT_ID
#   GCP_REGION
#   VERTEX_AI_LOCATION
#   GOOGLE_APPLICATION_CREDENTIALS (local dev)
#   GCS_BUCKET
```

---

## Step 3: Provision Infrastructure (Terraform)

```bash
cd deploy/terraform

# Initialize Terraform
terraform init

# Preview changes
terraform plan -var="project_id=YOUR_PROJECT_ID"

# Apply infrastructure
terraform apply -var="project_id=YOUR_PROJECT_ID"

# Note the outputs:
#   - cloud_run_url
#   - storage_bucket
#   - service_account_email
```

---

## Step 4: Local Development Setup

### Python Orchestrator
```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run orchestrator
python -m src.orchestrator.main
```

### Rust System Layer
```bash
cd src/system_layer

# Build
cargo build --release

# Run gRPC server
./target/release/omnicompanion-system
```

### Electron UI
```bash
cd src/ui

# Install dependencies
npm install

# Run in development mode
npm run dev
```

---

## Step 5: Cloud Deployment

```bash
# Make deploy script executable
chmod +x deploy/cloud_run_deploy.sh

# Deploy to Cloud Run
./deploy/cloud_run_deploy.sh

# With specific tag:
./deploy/cloud_run_deploy.sh v1.0.0
```

---

## Step 6: Verify Deployment

```bash
# Check Cloud Run service
gcloud run services describe omnicompanion-orchestrator \
  --region=us-central1 \
  --format="value(status.url)"

# Check logs
gcloud logging read "logName=projects/YOUR_PROJECT_ID/logs/omnicompanion-audit" \
  --limit=10

# Check Firestore
# Visit: https://console.cloud.google.com/firestore
```

---

## Troubleshooting

| Issue | Solution |
|-------|---------|
| `PermissionDenied` on Vertex AI | Ensure service account has `roles/aiplatform.user` |
| Firestore not found | Run `terraform apply` to create database |
| Docker build fails | Check `requirements.txt` for correct versions |
| gRPC connection refused | Ensure Rust system layer is running on port 50051 |
| Cloud Run 503 | Check min instances is set to 1 (cold start issue) |
