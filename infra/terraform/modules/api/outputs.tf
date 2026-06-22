output "service_url" {
  value = var.deploy_service ? "https://${aws_apprunner_service.api[0].service_url}" : ""
}

output "service_arn" {
  value = var.deploy_service ? aws_apprunner_service.api[0].arn : ""
}

output "service_security_group_id" {
  value = aws_security_group.service.id
}
