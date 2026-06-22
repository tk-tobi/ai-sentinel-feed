output "raw_bucket_name" {
  value = module.storage.raw_bucket_name
}

output "exports_bucket_name" {
  value = module.storage.exports_bucket_name
}

output "rds_endpoint" {
  value = module.database.endpoint
}

output "database_url" {
  value     = module.database.database_url
  sensitive = true
}

output "ingest_ecr_repository_url" {
  value = module.ecr.ingest_repository_url
}

output "api_ecr_repository_url" {
  value = module.ecr.api_repository_url
}

output "ecs_cluster_name" {
  value = module.ecs_ingest.cluster_name
}

output "ingest_task_definition_arn" {
  value = module.ecs_ingest.task_definition_arn
}

output "ingest_log_group_name" {
  value = module.ecs_ingest.log_group_name
}

output "eventbridge_rule_name" {
  value = module.ecs_ingest.eventbridge_rule_name
}

output "api_service_url" {
  value = module.api.service_url
}

output "app_secrets_arn" {
  value = module.secrets.app_secrets_arn
}

output "run_ingest_task_command" {
  description = "Manually trigger a one-off historical ingest on ECS"
  value       = module.ecs_ingest.run_task_cli_hint
}
