output "cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "task_definition_arn" {
  value = aws_ecs_task_definition.ingest.arn
}

output "task_security_group_id" {
  value = aws_security_group.task.id
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.ingest.name
}

output "eventbridge_rule_name" {
  value = aws_cloudwatch_event_rule.ingest.name
}

output "run_task_cli_hint" {
  value = "aws ecs run-task --cluster ${aws_ecs_cluster.this.name} --launch-type FARGATE --task-definition ${aws_ecs_task_definition.ingest.family} --network-configuration \"awsvpcConfiguration={subnets=[SUBNET_ID],securityGroups=[${aws_security_group.task.id}],assignPublicIp=ENABLED}\""
}
