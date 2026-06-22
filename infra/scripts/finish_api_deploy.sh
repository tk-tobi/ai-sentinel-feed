#!/usr/bin/env bash
# Finish production deploy after a partial apply (App Runner CREATE_FAILED) or image refresh.
#
# Usage:
#   ./infra/scripts/finish_api_deploy.sh dev
#   ./infra/scripts/finish_api_deploy.sh dev --skip-push   # API image already in ECR
set -euo pipefail

ENVIRONMENT="${1:-dev}"
shift || true

SKIP_PUSH=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-push)
      SKIP_PUSH=1
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${ROOT_DIR}/.." && pwd)"
TF_DIR="${REPO_ROOT}/infra/terraform/environments/${ENVIRONMENT}"

# shellcheck disable=SC1091
source "${ROOT_DIR}/scripts/aws_env.sh"
ensure_aws_credentials

if [[ "${SKIP_PUSH}" -eq 0 ]]; then
  echo "==> Pushing API image to ECR (ingest deferred — use push_ecr.sh --ingest-only later)"
  "${REPO_ROOT}/infra/scripts/push_ecr.sh" "${ENVIRONMENT}" --api-only
else
  echo "==> Skipping ECR push (--skip-push)"
fi

cd "${TF_DIR}"

AWS_REGION="$(terraform console <<< 'var.aws_region' 2>/dev/null | tr -d '"' || true)"
AWS_REGION="${AWS_REGION:-us-east-2}"
SERVICE_NAME="ai-sentinel-feed-${ENVIRONMENT}-api"

service_status() {
  aws apprunner list-services --region "${AWS_REGION}" \
    --query "ServiceSummaryList[?ServiceName=='${SERVICE_NAME}'].Status | [0]" \
    --output text 2>/dev/null || true
}

echo "==> Waiting for App Runner to finish any in-flight operation"
for _ in $(seq 1 60); do
  status="$(service_status)"
  if [[ -z "${status}" || "${status}" == "None" ]]; then
    break
  fi
  if [[ "${status}" != "OPERATION_IN_PROGRESS" ]]; then
    echo "    App Runner status: ${status}"
    break
  fi
  echo "    App Runner status: OPERATION_IN_PROGRESS (waiting 15s)"
  sleep 15
done

status="$(service_status)"
addr='module.api.aws_apprunner_service.api[0]'

if [[ "${status}" == "RUNNING" ]]; then
  echo "==> Service is RUNNING — clearing taint so Terraform does not replace it"
  terraform untaint "${addr}" 2>/dev/null || true
elif [[ "${status}" == "CREATE_FAILED" ]]; then
  if terraform state show "${addr}" &>/dev/null; then
    echo "==> Removing CREATE_FAILED App Runner from state for clean recreate"
    terraform state rm "${addr}"
  fi
elif [[ "${status}" == "OPERATION_IN_PROGRESS" ]]; then
  echo "App Runner is still OPERATION_IN_PROGRESS. Wait a few minutes and rerun:" >&2
  echo "  ./infra/scripts/finish_api_deploy.sh ${ENVIRONMENT} --skip-push" >&2
  exit 1
fi

echo "==> Applying App Runner service"
terraform plan -out=tfplan-api -var="deploy_api_service=true"
terraform apply -auto-approve tfplan-api

echo ""
terraform output api_service_url
