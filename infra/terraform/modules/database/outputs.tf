output "endpoint" {
  value = aws_db_instance.this.address
}

output "port" {
  value = aws_db_instance.this.port
}

output "database_url" {
  value     = "postgresql://${aws_db_instance.this.username}:${var.db_password}@${aws_db_instance.this.address}:${aws_db_instance.this.port}/${aws_db_instance.this.db_name}"
  sensitive = true
}

output "security_group_id" {
  value = aws_security_group.rds.id
}
