locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

module "storage" {
  source = "../../modules/storage"

  name_prefix   = local.name_prefix
  force_destroy = var.s3_force_destroy
}

module "database" {
  source = "../../modules/database"

  name_prefix         = local.name_prefix
  vpc_id              = data.aws_vpc.default.id
  subnet_ids          = data.aws_subnets.default.ids
  db_name             = var.db_name
  db_username         = var.db_username
  db_password         = var.db_password
  instance_class      = var.db_instance_class
  skip_final_snapshot = var.db_skip_final_snapshot
}

module "ecr" {
  source = "../../modules/ecr"

  name_prefix = local.name_prefix
}

module "secrets" {
  source = "../../modules/secrets"

  name_prefix    = local.name_prefix
  database_url   = module.database.database_url
  nvd_api_key    = var.nvd_api_key
  hf_token       = var.hf_token
  aiaaic_csv_url = var.aiaaic_csv_url
}

module "ecs_ingest" {
  source = "../../modules/ecs_ingest"

  name_prefix                = local.name_prefix
  aws_region                 = var.aws_region
  vpc_id                     = data.aws_vpc.default.id
  subnet_ids                 = data.aws_subnets.default.ids
  ecr_repository_url         = module.ecr.ingest_repository_url
  schedule_expression        = var.ingest_schedule_expression
  cpu                        = var.ingest_cpu
  memory                     = var.ingest_memory
  secrets_arn                = module.secrets.app_secrets_arn
  raw_bucket_name            = module.storage.raw_bucket_name
  exports_bucket_name        = module.storage.exports_bucket_name
  database_security_group_id = module.database.security_group_id
}

module "api" {
  source = "../../modules/api"

  name_prefix                = local.name_prefix
  aws_region                 = var.aws_region
  vpc_id                     = data.aws_vpc.default.id
  subnet_ids                 = data.aws_subnets.default.ids
  ecr_repository_url         = module.ecr.api_repository_url
  cpu                        = var.api_cpu
  memory                     = var.api_memory
  secrets_arn                = module.secrets.app_secrets_arn
  database_security_group_id = module.database.security_group_id
  deploy_service             = var.deploy_api_service
}

resource "aws_security_group_rule" "rds_from_ingest" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = module.database.security_group_id
  source_security_group_id = module.ecs_ingest.task_security_group_id
}

resource "aws_security_group_rule" "rds_from_api" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = module.database.security_group_id
  source_security_group_id = module.api.service_security_group_id
}
