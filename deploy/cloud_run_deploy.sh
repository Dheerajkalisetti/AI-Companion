#!/bin/bash
# OmniCompanion — Cloud Run Deployment Script
# Builds and deploys the Python orchestrator to Cloud Run

set -euo pipefail

# ──────────────────────────────────────
# Configuration
# ──────────────────────────────────────
PROJECT_ID="${GCP_PROJECT_ID:?'GCP_PROJECT_ID environment variable required'}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="omnicompanion-orchestrator"
IMAGE_NAME="orchestrator"
REPO_NAME="omnicompanion"
IMAGE_TAG="${1:-latest}"

FULL_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:${IMAGE_TAG}"

echo "═══════════════════════════════════════"
echo "  OmniCompanion Cloud Run Deployment"
echo "═══════════════════════════════════════"
echo ""
echo "  Project:  ${PROJECT_ID}"
echo "  Region:   ${REGION}"
echo "  Service:  ${SERVICE_NAME}"
echo "  Image:    ${FULL_IMAGE}"
echo ""

# ──────────────────────────────────────
# Step 1: Authenticate
# ──────────────────────────────────────
echo "→ Step 1: Configuring Docker authentication..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# ──────────────────────────────────────
# Step 2: Build Docker image
# ──────────────────────────────────────
echo "→ Step 2: Building Docker image..."
docker build -f deploy/Dockerfile.orchestrator -t "${FULL_IMAGE}" .

# ──────────────────────────────────────
# Step 3: Push to Artifact Registry
# ──────────────────────────────────────
echo "→ Step 3: Pushing image to Artifact Registry..."
docker push "${FULL_IMAGE}"

# ──────────────────────────────────────
# Step 4: Deploy to Cloud Run
# ──────────────────────────────────────
echo "→ Step 4: Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image="${FULL_IMAGE}" \
  --region="${REGION}" \
  --platform=managed \
  --min-instances=1 \
  --max-instances=10 \
  --memory=2Gi \
  --cpu=2 \
  --concurrency=1 \
  --timeout=300 \
  --port=8080 \
  --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=${REGION},VERTEX_AI_LOCATION=${REGION},ENVIRONMENT=production" \
  --service-account="omnicompanion-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --no-allow-unauthenticated \
  --quiet

# ──────────────────────────────────────
# Step 5: Get service URL
# ──────────────────────────────────────
echo ""
echo "→ Step 5: Fetching service URL..."
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --region="${REGION}" \
  --format="value(status.url)")

echo ""
echo "═══════════════════════════════════════"
echo "  ✅ Deployment Complete!"
echo "  URL: ${SERVICE_URL}"
echo "═══════════════════════════════════════"
