#!/usr/bin/env bash
# Pull the latest :latest API image from ECR into App Runner (auto_deploy is off).
#
# Usage:
#   ./infra/scripts/redeploy_api.sh dev
set -euo pipefail

ENVIRONMENT="${1:-dev}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${ROOT_DIR}/.." && pwd)"
TF_DIR="${REPO_ROOT}/infra/terraform/environments/${ENVIRONMENT}"

# shellcheck disable=SC1091
source "${ROOT_DIR}/scripts/aws_env.sh"
ensure_aws_credentials

cd "${TF_DIR}"

AWS_REGION="$(terraform output -raw aws_region 2>/dev/null || echo us-east-2)"
SERVICE_ARN="$(terraform output -raw api_service_arn 2>/dev/null || true)"

if [[ -z "${SERVICE_ARN}" ]]; then
  SERVICE_ARN="$(aws apprunner list-services --region "${AWS_REGION}" \
    --query 'ServiceSummaryList[?ServiceName==`ai-sentinel-feed-'${ENVIRONMENT}'-api`].ServiceArn | [0]' \
    --output text)"
fi

if [[ -z "${SERVICE_ARN}" || "${SERVICE_ARN}" == "None" ]]; then
  echo "Could not resolve App Runner service ARN." >&2
  exit 1
fi

echo "==> Starting App Runner deployment"
echo "    Region: ${AWS_REGION}"
echo "    ARN:    ${SERVICE_ARN}"

OP_ID="$(aws apprunner start-deployment \
  --region "${AWS_REGION}" \
  --service-arn "${SERVICE_ARN}" \
  --query 'OperationId' \
  --output text)"

echo "    OperationId: ${OP_ID}"
echo ""
echo "Wait ~2–5 min, then:"
echo "  curl $(terraform output -raw api_service_url)/health"
echo "  curl $(terraform output -raw api_service_url)/incidents?page_size=1"
