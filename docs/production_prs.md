# Production deployment, PR plan

Split work across focused PRs on `feat/production-deploy` (or stacked branches).

## PR 1, Production Docker images + ECR push *(this branch, first)*

**Goal:** Buildable API and ingest images matching Terraform ECR repos.

| File | Purpose |
|------|---------|
| `docker/Dockerfile.api` | Slim FastAPI for App Runner |
| `docker/Dockerfile.ingest` | Playwright + ingest for ECS Fargate |
| `requirements/api.txt`, `requirements/ingest.txt` | Image-specific deps |
| `infra/scripts/push_ecr.sh` | Build + push to ECR after `terraform apply` |

**After merge:** `terraform apply` → `./infra/scripts/push_ecr.sh dev`

---

## PR 2, Terraform apply + production smoke test

**Goal:** Live AWS dev stack.

- Run `./infra/scripts/apply.sh dev` (tfvars already configured)
- Push images (PR 1)
- Trigger App Runner deployment for API image
- Verify `terraform output api_service_url` → `/health`

No code required unless apply surfaces module fixes.

---

## PR 3, RDS historical load

**Goal:** Seed production Postgres without re-scraping from laptop.

- Run ECS one-off ingest task (`scripts/historical_load_rds.sh`)
- Or: `python -m sentinel.pipeline.seed` pointed at RDS if bastion added
- Verify counts via API `/incidents/stats`

---

## PR 4, S3 export hooks + scheduled ingest hardening

**Goal:** Post-ingest uploads to S3; nightly schedule verified.

- S3 upload in `ingest.py` or post-ingest hook (`AWS_RAW_BUCKET`, `AWS_EXPORTS_BUCKET`)
- Export JSONL after ingest in ECS task command chain

---

## PR 5, Streamlit Cloud + HuggingFace Hub

**Goal:** Public dashboard and ML dataset access.

- Streamlit Cloud secrets → `DATABASE_URL` or API URL
- HF Hub publish from exports manifest

---

## Image matrix

| Image | Registry | Use |
|-------|----------|-----|
| `ghcr.io/tk-tobi/ai-sentinel-feed` | GHCR | Local one-step demo (Postgres + API + dashboard) |
| `*-api` ECR | AWS | App Runner production API |
| `*-ingest` ECR | AWS | ECS Fargate scheduled ingest |
