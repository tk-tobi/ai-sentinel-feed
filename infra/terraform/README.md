# AWS infrastructure (Terraform)

Provisions AWS resources for **ai-sentinel-feed** production deployment:

| Module | AWS services |
|---|---|
| `storage` | S3 (raw + exports) |
| `database` | RDS PostgreSQL |
| `ecr` | ECR repositories (ingest + API images) |
| `ecs_ingest` | ECS cluster, Fargate task, EventBridge schedule, CloudWatch Logs |
| `api` | App Runner (read-only FastAPI) |
| `secrets` | Secrets Manager (DB URL, API keys) |

**Not provisioned here:** Streamlit Cloud (hosted separately), HuggingFace Hub (dataset publish from ingest job).

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- AWS CLI configured (`aws configure`)
- IAM permissions for RDS, S3, ECS, ECR, App Runner, Secrets Manager, EventBridge, IAM

## Quick start (dev)

```bash
cd infra/terraform/environments/dev

cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — set db_password, aws_region

terraform init
terraform plan
terraform apply
```

## Teardown

Dev defaults are teardown-friendly (`skip_final_snapshot`, `force_destroy` on buckets).

```bash
cd infra/terraform/environments/dev
terraform destroy
```

Or use the helper script from repo root:

```bash
./infra/scripts/teardown.sh dev
```

## GCP mapping

See [TODO.md](../../../TODO.md) — AWS ↔ GCP equivalence table in the production architecture section.

## After apply

1. Push production images to ECR:
   ```bash
   ./infra/scripts/push_ecr.sh dev
   ```
2. Redeploy App Runner to pick up the new API image (auto-deploy is off).
3. Run a one-off ECS ingest task for RDS historical load (`scripts/historical_load_rds.sh`).
4. Deploy Streamlit Cloud with `DATABASE_URL` or the public API URL.
5. Publish exports to HuggingFace Hub.

Production image definitions: `docker/Dockerfile.api`, `docker/Dockerfile.ingest`.  
PR plan: [`docs/production_prs.md`](../../docs/production_prs.md).

## State

Remote state (S3 backend) is optional. Dev uses local state by default. Uncomment `backend "s3"` in `versions.tf` for team use.
