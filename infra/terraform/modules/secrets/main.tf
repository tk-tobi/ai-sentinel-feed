variable "name_prefix" {
  type = string
}

variable "database_url" {
  type      = string
  sensitive = true
}

variable "nvd_api_key" {
  type      = string
  sensitive = true
}

variable "hf_token" {
  type      = string
  sensitive = true
}

variable "aiaaic_csv_url" {
  type = string
}

resource "aws_secretsmanager_secret" "app" {
  name = "${var.name_prefix}/app"
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    DATABASE_URL   = var.database_url
    NVD_API_KEY    = var.nvd_api_key
    HF_TOKEN       = var.hf_token
    AIAAIC_CSV_URL = var.aiaaic_csv_url
  })
}
