# OmniCompanion — Terraform Configuration
# Provisions all GCP infrastructure for the project

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.10"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ──────────────────────────────────────
# Service Account
# ──────────────────────────────────────
resource "google_service_account" "omnicompanion_sa" {
  account_id   = "omnicompanion-sa"
  display_name = "OmniCompanion Service Account"
  description  = "Service account for OmniCompanion orchestrator"
}

resource "google_project_iam_member" "vertex_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.omnicompanion_sa.email}"
}

resource "google_project_iam_member" "firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.omnicompanion_sa.email}"
}

resource "google_project_iam_member" "storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.omnicompanion_sa.email}"
}

resource "google_project_iam_member" "logging_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.omnicompanion_sa.email}"
}

resource "google_project_iam_member" "run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.omnicompanion_sa.email}"
}

# ──────────────────────────────────────
# Enable Required APIs
# ──────────────────────────────────────
resource "google_project_service" "vertex_ai" {
  service            = "aiplatform.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloud_run" {
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "firestore" {
  service            = "firestore.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloud_storage" {
  service            = "storage.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloud_logging" {
  service            = "logging.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "artifact_registry" {
  service            = "artifactregistry.googleapis.com"
  disable_on_destroy = false
}

# ──────────────────────────────────────
# Cloud Storage Bucket
# ──────────────────────────────────────
resource "google_storage_bucket" "artifacts" {
  name          = "${var.project_id}-omnicompanion-artifacts"
  location      = var.region
  storage_class = "STANDARD"
  force_destroy = false

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 30  # Auto-delete screenshots after 30 days
    }
    action {
      type = "Delete"
    }
  }
}

# ──────────────────────────────────────
# Firestore Database
# ──────────────────────────────────────
resource "google_firestore_database" "default" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.firestore_location
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.firestore]
}

# ──────────────────────────────────────
# Artifact Registry (Docker)
# ──────────────────────────────────────
resource "google_artifact_registry_repository" "docker" {
  location      = var.region
  repository_id = "omnicompanion"
  description   = "Docker images for OmniCompanion"
  format        = "DOCKER"

  depends_on = [google_project_service.artifact_registry]
}

# ──────────────────────────────────────
# Cloud Run Service
# ──────────────────────────────────────
resource "google_cloud_run_v2_service" "orchestrator" {
  name     = "omnicompanion-orchestrator"
  location = var.region

  template {
    scaling {
      min_instance_count = var.cloud_run_min_instances
      max_instance_count = var.cloud_run_max_instances
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/omnicompanion/orchestrator:latest"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "VERTEX_AI_LOCATION"
        value = var.region
      }
      env {
        name  = "GCS_BUCKET"
        value = google_storage_bucket.artifacts.name
      }
      env {
        name  = "ENVIRONMENT"
        value = "production"
      }
    }

    service_account = google_service_account.omnicompanion_sa.email
    timeout         = "300s"
  }

  depends_on = [
    google_project_service.cloud_run,
    google_artifact_registry_repository.docker,
  ]
}

# ──────────────────────────────────────
# Cloud Logging Sink (Optional — for export)
# ──────────────────────────────────────
resource "google_logging_project_sink" "audit_sink" {
  name        = "omnicompanion-audit-sink"
  destination = "storage.googleapis.com/${google_storage_bucket.artifacts.name}"
  filter      = "logName=\"projects/${var.project_id}/logs/omnicompanion-audit\""

  unique_writer_identity = true
}
