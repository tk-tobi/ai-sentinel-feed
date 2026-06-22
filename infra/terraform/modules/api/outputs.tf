output "service_url" {
  value = "https://${aws_apprunner_service.api.service_url}"
}

output "service_security_group_id" {
  value = aws_security_group.service.id
}
