variable "name_prefix" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "db_name" {
  type = string
}

variable "db_username" {
  type = string
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "instance_class" {
  type = string
}

variable "skip_final_snapshot" {
  type = bool
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-db-subnets"
  subnet_ids = var.subnet_ids
}

resource "aws_security_group" "rds" {
  name        = "${var.name_prefix}-rds"
  description = "PostgreSQL access for ai-sentinel-feed"
  vpc_id      = var.vpc_id
}

resource "aws_db_instance" "this" {
  identifier              = "${var.name_prefix}-postgres"
  engine                  = "postgres"
  engine_version          = "16"
  instance_class          = var.instance_class
  allocated_storage       = 20
  max_allocated_storage   = 100
  storage_type            = "gp3"
  db_name                 = var.db_name
  username                = var.db_username
  password                = var.db_password
  db_subnet_group_name    = aws_db_subnet_group.this.name
  vpc_security_group_ids  = [aws_security_group.rds.id]
  publicly_accessible     = false
  backup_retention_period = 7
  skip_final_snapshot     = var.skip_final_snapshot
  deletion_protection     = false
  apply_immediately       = true
}
