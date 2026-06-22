#!/usr/bin/env bash
# Run historical ingest on RDS via ECS Fargate (RDS is not publicly accessible).
#
# Prerequisites:
#   - terraform apply in infra/terraform/environments/dev
#   - ingest Docker image pushed to ECR (:latest)
#   - aws CLI authenticated
#
# Usage:
#   ./scripts/historical_load_rds.sh [dev]
set -euo pipefail

ENVIRONMENT="${1:-dev}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT_DIR}/infra/terraform/environments/${ENVIRONMENT}"

# shellcheck disable=SC1091
source "${ROOT_DIR}/infra/scripts/aws_env.sh"
ensure_aws_credentials

if [[ ! -d "${TF_DIR}" ]]; then
  echo "Unknown environment: ${ENVIRONMENT}" >&2
  exit 1
fi

cd "${TF_DIR}"

CLUSTER="$(terraform output -raw ecs_cluster_name)"
TASK_DEF="$(terraform output -raw ingest_task_definition_arn)"
SG="$(terraform output -raw ingest_task_security_group_id 2>/dev/null || true)"

if [[ -z "${SG}" ]]; then
  echo "Could not read ingest task security group from terraform output." >&2
  exit 1
fi

# Default VPC subnet (matches terraform dev layout — assignPublicIp for ECR/NVD egress).
SUBNET="${SUBNET_ID:-}"
if [[ -z "${SUBNET}" ]]; then
  SUBNET="$(aws ec2 describe-subnets \
    --filters "Name=default-for-az,Values=true" \
    --query 'Subnets[0].SubnetId' \
    --output text)"
fi

if [[ -z "${SUBNET}" || "${SUBNET}" == "None" ]]; then
  echo "Could not resolve a subnet. Export SUBNET_ID and re-run." >&2
  exit 1
fi

echo "Cluster:     ${CLUSTER}"
echo "Task def:    ${TASK_DEF}"
echo "Subnet:      ${SUBNET}"
echo "SecurityGrp: ${SG}"
echo ""
echo "Starting one-off historical ingest (all sources)..."

TASK_ARN="$(aws ecs run-task \
  --cluster "${CLUSTER}" \
  --launch-type FARGATE \
  --task-definition "${TASK_DEF}" \
  --network-configuration "awsvpcConfiguration={subnets=[${SUBNET}],securityGroups=[${SG}],assignPublicIp=ENABLED}" \
  --query 'tasks[0].taskArn' \
  --output text)"

echo "Task ARN: ${TASK_ARN}"
echo ""
LOG_GROUP="$(terraform output -raw ingest_log_group_name)"
echo "Tail logs:"
echo "  aws logs tail ${LOG_GROUP} --follow --region $(terraform output -raw aws_region)"
echo ""
echo "Waiting for task to finish (this can take 30–90 minutes for a full historical load)..."
aws ecs wait tasks-stopped --cluster "${CLUSTER}" --tasks "${TASK_ARN}"

EXIT_CODE="$(aws ecs describe-tasks \
  --cluster "${CLUSTER}" \
  --tasks "${TASK_ARN}" \
  --query 'tasks[0].containers[0].exitCode' \
  --output text)"
echo "Task exit code: ${EXIT_CODE}"

if [[ "${EXIT_CODE}" != "0" ]]; then
  echo "Ingest task failed. Check CloudWatch logs above." >&2
  exit 1
fi

echo "Historical ingest complete. Verify API:"
API_URL="$(terraform output -raw api_service_url)"
echo "  curl ${API_URL}/incidents?page_size=1"
