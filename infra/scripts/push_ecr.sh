#!/usr/bin/env bash
# Build and push production API + ingest images to ECR.
#
# Prerequisites:
#   - terraform apply in infra/terraform/environments/<env>
#   - docker running
#   - aws CLI authenticated
#
# Usage:
#   ./infra/scripts/push_ecr.sh dev
#   ./infra/scripts/push_ecr.sh dev --api-only
#   ./infra/scripts/push_ecr.sh dev --ingest-only
set -euo pipefail

ENVIRONMENT="${1:-dev}"
shift || true

PUSH_API=1
PUSH_INGEST=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-only)
      PUSH_INGEST=0
      shift
      ;;
    --ingest-only)
      PUSH_API=0
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="${ROOT_DIR}/infra/terraform/environments/${ENVIRONMENT}"

# shellcheck disable=SC1091
source "${ROOT_DIR}/infra/scripts/aws_env.sh"
ensure_aws_credentials

if [[ ! -d "${TF_DIR}" ]]; then
  echo "Unknown environment: ${ENVIRONMENT}" >&2
  exit 1
fi

cd "${ROOT_DIR}"

API_REPO="$(terraform -chdir="${TF_DIR}" output -raw api_ecr_repository_url)"
INGEST_REPO="$(terraform -chdir="${TF_DIR}" output -raw ingest_ecr_repository_url)"

# Region is embedded in the ECR URL (avoids terraform console warnings on partial state).
ecr_region_from_url() {
  echo "$1" | sed -E 's#.*\.ecr\.([^.]+)\.amazonaws\.com.*#\1#'
}
AWS_REGION="${AWS_REGION:-$(ecr_region_from_url "${API_REPO}")}"
if [[ -z "${AWS_REGION}" || "${AWS_REGION}" == "${API_REPO}" ]]; then
  AWS_REGION="$(terraform -chdir="${TF_DIR}" output -raw aws_region 2>/dev/null || true)"
fi
AWS_REGION="${AWS_REGION:-$(aws configure get region)}"

if [[ -z "${AWS_REGION}" ]]; then
  echo "Set AWS_REGION or configure aws CLI default region." >&2
  exit 1
fi

REGISTRY="${API_REPO%%/*}"

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop, wait until it is ready, then retry." >&2
  exit 1
fi

echo "==> Fetching ECR login password (region ${AWS_REGION})"
PASSWORD="$(aws ecr get-login-password --region "${AWS_REGION}")"
if [[ -z "${PASSWORD}" ]]; then
  echo "ECR login password was empty. Refresh AWS credentials:" >&2
  echo "  aws login" >&2
  echo '  eval "$(aws configure export-credentials --format env)"' >&2
  exit 1
fi

echo "==> Logging in to ECR (${REGISTRY})"
echo "${PASSWORD}" | docker login --username AWS --password-stdin "${REGISTRY}"
echo "==> ECR login OK"

if [[ "${PUSH_API}" -eq 1 ]]; then
  echo "==> Building API image -> ${API_REPO}:latest"
  docker build --platform linux/amd64 -f docker/Dockerfile.api -t "${API_REPO}:latest" .
  docker push "${API_REPO}:latest"
  echo "==> Pushed ${API_REPO}:latest"
fi

if [[ "${PUSH_INGEST}" -eq 1 ]]; then
  echo "==> Building ingest image -> ${INGEST_REPO}:latest"
  docker build --platform linux/amd64 -f docker/Dockerfile.ingest -t "${INGEST_REPO}:latest" .
  docker push "${INGEST_REPO}:latest"
  echo "==> Pushed ${INGEST_REPO}:latest"
fi

echo ""
echo "Done. App Runner uses the API image; ECS scheduled task uses ingest."
echo "Redeploy App Runner manually after push (auto_deployments_enabled=false)."
