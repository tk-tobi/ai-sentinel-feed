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

echo "This will destroy all resources in environment: ${ENVIRONMENT}"
read -r -p "Type the environment name to confirm teardown: " CONFIRM

if [[ "${CONFIRM}" != "${ENVIRONMENT}" ]]; then
  echo "Aborted."
  exit 1
fi

terraform destroy

echo "Teardown complete for ${ENVIRONMENT}."
