variable "aws_region" {
  type        = string
  description = "AWS region for all resources"
  default     = "us-east-1"
}

variable "project_name" {
  type        = string
  description = "Short project prefix for resource names"
  default     = "ai-sentinel-feed"
}

variable "environment" {
  type        = string
  description = "Deployment environment label"
  default     = "dev"
}

variable "db_name" {
  type        = string
  description = "PostgreSQL database name"
  default     = "sentinel"
}

variable "db_username" {
  type        = string
  description = "PostgreSQL master username"
  default     = "sentinel"
}

variable "db_password" {
  type        = string
  description = "PostgreSQL master password"
  sensitive   = true
}

variable "db_instance_class" {
  type        = string
  description = "RDS instance class"
  default     = "db.t4g.micro"
}

variable "db_skip_final_snapshot" {
  type        = bool
  description = "Skip RDS final snapshot on destroy (set true for dev teardown)"
  default     = true
}

variable "s3_force_destroy" {
  type        = bool
  description = "Allow non-empty S3 buckets to be destroyed"
  default     = true
}

variable "ingest_schedule_expression" {
  type        = string
  description = "EventBridge schedule for nightly ingest (UTC)"
  default     = "cron(0 6 * * ? *)"
}

variable "ingest_cpu" {
  type    = number
  default = 1024
}

variable "ingest_memory" {
  type    = number
  default = 2048
}

variable "api_cpu" {
  type    = string
  default = "1024"
}

variable "api_memory" {
  type    = string
  default = "2048"
}

variable "nvd_api_key" {
  type        = string
  description = "NVD API key (optional placeholder for Secrets Manager)"
  sensitive   = true
  default     = ""
}

variable "hf_token" {
  type        = string
  description = "HuggingFace Hub token for dataset publish"
  sensitive   = true
  default     = ""
}

variable "aiaaic_csv_url" {
  type        = string
  description = "AIAAIC Google Sheets CSV export URL"
  default     = "https://docs.google.com/spreadsheets/d/1Bn55B4xz21-_Rgdr8BBb2lt0n_4rzLGxFADMlVW0PYI/export?format=csv&gid=888071280"
}

variable "deploy_api_service" {
  type        = bool
  description = "Create App Runner API service (set false for phase-1 apply before ECR push)"
  default     = false
}
