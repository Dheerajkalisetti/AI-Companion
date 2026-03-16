# OmniCompanion — Terraform Variables

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region for all services"
  type        = string
  default     = "us-central1"
}

variable "firestore_location" {
  description = "Firestore database location"
  type        = string
  default     = "nam5"  # Multi-region US
}

variable "cloud_run_min_instances" {
  description = "Minimum number of Cloud Run instances"
  type        = number
  default     = 1
}

variable "cloud_run_max_instances" {
  description = "Maximum number of Cloud Run instances"
  type        = number
  default     = 10
}
