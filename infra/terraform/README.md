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
- AWS CLI configured (`aws login` or `aws configure`)
- IAM permissions for RDS, S3, ECS, ECR, App Runner, Secrets Manager, EventBridge, IAM

**Terraform + `aws login`:** The AWS provider does not read `aws login` sessions directly. Our scripts call `aws configure export-credentials` first. If you run `terraform` manually:

```bash
aws login
eval "$(aws configure export-credentials --format env)"
terraform plan
```

Set `aws_region` in `terraform.tfvars` to the region where you want resources (e.g. `us-east-2` if that is your default).

## Quick start (dev)

```bash
cd infra/terraform/environments/dev

cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — set db_password, aws_region

# From repo root (three phases: infra → ECR push → App Runner):
./infra/scripts/apply.sh dev
```

`apply.sh` skips App Runner on the first pass so ECR can receive images before the service is created.

**If App Runner already failed with `CREATE_FAILED`:**

```bash
./infra/scripts/finish_api_deploy.sh dev
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

1. Push production images to ECR (ingest image is large — use `--ingest-only` if API is already live):
   ```bash
   ./infra/scripts/push_ecr.sh dev --ingest-only
   ```
2. Redeploy App Runner after API image changes (`finish_api_deploy.sh` or `terraform apply -var=deploy_api_service=true`).
3. Run historical load into RDS:
   ```bash
   ./scripts/historical_load_rds.sh dev
   ```
4. Deploy Streamlit Cloud with the public API URL or `DATABASE_URL`.
5. Publish exports to HuggingFace Hub.

Production image definitions: `docker/Dockerfile.api`, `docker/Dockerfile.ingest`.  
PR plan: [`docs/production_prs.md`](../../docs/production_prs.md).

## State

Remote state (S3 backend) is optional. Dev uses local state by default. Uncomment `backend "s3"` in `versions.tf` for team use.
