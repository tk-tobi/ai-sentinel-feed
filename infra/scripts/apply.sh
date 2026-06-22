#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${1:-dev}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT_DIR}/terraform/environments/${ENVIRONMENT}"

if [[ ! -d "${TF_DIR}" ]]; then
  echo "Unknown environment: ${ENVIRONMENT}" >&2
  exit 1
fi

cd "${TF_DIR}"

if [[ ! -f terraform.tfvars ]]; then
  echo "Copy terraform.tfvars.example to terraform.tfvars and edit values first." >&2
  exit 1
fi

terraform init -upgrade
terraform plan -out=tfplan
terraform apply tfplan

echo ""
echo "Apply complete. Outputs:"
terraform output
