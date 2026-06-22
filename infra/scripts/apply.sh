#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${1:-dev}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${ROOT_DIR}/.." && pwd)"
TF_DIR="${REPO_ROOT}/infra/terraform/environments/${ENVIRONMENT}"

# shellcheck disable=SC1091
source "${ROOT_DIR}/scripts/aws_env.sh"
ensure_aws_credentials

if [[ ! -d "${TF_DIR}" ]]; then
  echo "Unknown environment: ${ENVIRONMENT}" >&2
  exit 1
fi

if [[ ! -f "${TF_DIR}/terraform.tfvars" ]]; then
  echo "Missing ${TF_DIR}/terraform.tfvars" >&2
  exit 1
fi

cd "${TF_DIR}"

echo "==> Phase 1: core infrastructure (App Runner service deferred until ECR has images)"
terraform init -upgrade
terraform plan -out=tfplan -var="deploy_api_service=false"
terraform apply tfplan

echo ""
echo "==> Phase 2: build and push API + ingest images to ECR"
"${REPO_ROOT}/infra/scripts/push_ecr.sh" "${ENVIRONMENT}"

echo ""
echo "==> Phase 3: App Runner API service"
terraform plan -out=tfplan-api -var="deploy_api_service=true"
terraform apply tfplan-api

echo ""
echo "Apply complete. Outputs:"
terraform output
