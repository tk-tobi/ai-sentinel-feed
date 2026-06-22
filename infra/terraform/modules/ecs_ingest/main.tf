variable "name_prefix" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "ecr_repository_url" {
  type = string
}

variable "schedule_expression" {
  type = string
}

variable "cpu" {
  type = number
}

variable "memory" {
  type = number
}

variable "secrets_arn" {
  type = string
}

variable "raw_bucket_name" {
  type = string
}

variable "exports_bucket_name" {
  type = string
}

variable "database_security_group_id" {
  type = string
}

resource "aws_ecs_cluster" "this" {
  name = "${var.name_prefix}-cluster"
}

resource "aws_cloudwatch_log_group" "ingest" {
  name              = "/ecs/${var.name_prefix}-ingest"
  retention_in_days = 14
}

resource "aws_security_group" "task" {
  name        = "${var.name_prefix}-ingest-task"
  description = "ECS Fargate ingest task"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_iam_role" "task_execution" {
  name = "${var.name_prefix}-ingest-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "task_execution" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "secrets_access" {
  name = "${var.name_prefix}-ingest-secrets"
  role = aws_iam_role.task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [var.secrets_arn]
    }]
  })
}

resource "aws_iam_role" "task" {
  name = "${var.name_prefix}-ingest-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "s3_access" {
  name = "${var.name_prefix}-ingest-s3"
  role = aws_iam_role.task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
      Resource = [
        "arn:aws:s3:::${var.raw_bucket_name}",
        "arn:aws:s3:::${var.raw_bucket_name}/*",
        "arn:aws:s3:::${var.exports_bucket_name}",
        "arn:aws:s3:::${var.exports_bucket_name}/*",
      ]
    }]
  })
}

resource "aws_ecs_task_definition" "ingest" {
  family                   = "${var.name_prefix}-ingest"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = "ingest"
    image     = "${var.ecr_repository_url}:latest"
    essential = true
    command   = ["python", "-m", "sentinel.pipeline.ingest", "--source", "all"]
    secrets = [
      { name = "DATABASE_URL", valueFrom = "${var.secrets_arn}:DATABASE_URL::" },
      { name = "NVD_API_KEY", valueFrom = "${var.secrets_arn}:NVD_API_KEY::" },
      { name = "HF_TOKEN", valueFrom = "${var.secrets_arn}:HF_TOKEN::" },
      { name = "AIAAIC_CSV_URL", valueFrom = "${var.secrets_arn}:AIAAIC_CSV_URL::" },
    ]
    environment = [
      { name = "AWS_RAW_BUCKET", value = var.raw_bucket_name },
      { name = "AWS_EXPORTS_BUCKET", value = var.exports_bucket_name },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.ingest.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ingest"
      }
    }
  }])
}

resource "aws_iam_role" "events" {
  name = "${var.name_prefix}-events"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "events_run_task" {
  name = "${var.name_prefix}-events-run-task"
  role = aws_iam_role.events.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ecs:RunTask"]
      Resource = [aws_ecs_task_definition.ingest.arn]
      }, {
      Effect = "Allow"
      Action = ["iam:PassRole"]
      Resource = [
        aws_iam_role.task_execution.arn,
        aws_iam_role.task.arn,
      ]
    }]
  })
}

resource "aws_cloudwatch_event_rule" "ingest" {
  name                = "${var.name_prefix}-ingest-daily"
  schedule_expression = var.schedule_expression
}

resource "aws_cloudwatch_event_target" "ingest" {
  rule      = aws_cloudwatch_event_rule.ingest.name
  target_id = "ingest"
  arn       = aws_ecs_cluster.this.arn
  role_arn  = aws_iam_role.events.arn

  ecs_target {
    task_count          = 1
    task_definition_arn = aws_ecs_task_definition.ingest.arn
    launch_type         = "FARGATE"
    platform_version    = "LATEST"

    network_configuration {
      subnets          = var.subnet_ids
      security_groups  = [aws_security_group.task.id]
      assign_public_ip = true
    }
  }
}
