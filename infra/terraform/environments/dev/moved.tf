# Migrate existing App Runner resources when deploy_service uses count.
moved {
  from = module.api.aws_apprunner_service.api
  to   = module.api.aws_apprunner_service.api[0]
}
