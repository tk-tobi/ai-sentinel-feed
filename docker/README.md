# All-in-one Docker image

Pre-built image: `**ghcr.io/tk-tobi/ai-sentinel-feed:latest**`

Contains embedded PostgreSQL, FastAPI, Streamlit, and a seed snapshot (`docker/seed/incidents.jsonl`, ~4.4k incidents). First boot loads seed data automatically; later restarts reuse the volume.

## For users (pull and run)

**One command** (Docker only — no clone, no build):

```bash
docker run -d \
  --name ai-sentinel-feed \
  -p 8000:8000 -p 8501:8501 \
  -v sentinel_pgdata:/var/lib/postgresql/data \
  ghcr.io/tk-tobi/ai-sentinel-feed:latest
```

Or with Compose (from a clone, or after downloading `docker-compose.local.yml`):

```bash
docker compose -f docker-compose.local.yml up -d
```


| Service   | URL                                                      |
| --------- | -------------------------------------------------------- |
| API       | [http://localhost:8000](http://localhost:8000)           |
| API docs  | [http://localhost:8000/docs](http://localhost:8000/docs) |
| Dashboard | [http://localhost:8501](http://localhost:8501)           |


**Fresh DB + re-seed:** `docker compose -f docker-compose.local.yml down -v` then `up -d` again.

> **First publish:** Until CI pushes the image to GHCR, maintainers must build locally (see below) or wait for the `Publish Docker image` workflow on `main`. Make the package **public** under GitHub → Packages after the first successful run.

## For maintainers (build from source)

The Dockerfile stays in the repo so builds are reproducible and reviewable. Consumers do not need it.

```bash
# Refresh seed after a new historical load
./scripts/export_docker_seed.sh

# Build and run locally
docker compose -f docker-compose.local.yml -f docker-compose.build.yml up --build
```

CI (`.github/workflows/docker-publish.yml`) builds and pushes to GHCR on pushes to `main` and version tags.

## What is not in this image

- **Ingest / Playwright** — run locally with Python for full re-scrape (`python -m sentinel.pipeline.ingest`)
- The standalone `docker-compose.yml` (Postgres-only) remains for that dev workflow

## Production images (AWS)

| Dockerfile | Target | Command |
|------------|--------|---------|
| `Dockerfile.api` | App Runner (ECR) | `uvicorn sentinel.api.main:app` |
| `Dockerfile.ingest` | ECS Fargate (ECR) | `python -m sentinel.pipeline.ingest --source all` |

After `terraform apply`:

```bash
./infra/scripts/push_ecr.sh dev
```

See [`docs/production_prs.md`](../docs/production_prs.md) for the full production PR plan.

