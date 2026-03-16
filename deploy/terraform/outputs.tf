# OmniCompanion — Terraform Outputs

output "service_account_email" {
  description = "OmniCompanion service account email"
  value       = google_service_account.omnicompanion_sa.email
}

output "cloud_run_url" {
  description = "Cloud Run service URL"
  value       = google_cloud_run_v2_service.orchestrator.uri
}

output "storage_bucket" {
  description = "Cloud Storage bucket name"
  value       = google_storage_bucket.artifacts.name
}

output "artifact_registry" {
  description = "Artifact Registry Docker repository"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/omnicompanion"
}

output "firestore_database" {
  description = "Firestore database name"
  value       = google_firestore_database.default.name
}
