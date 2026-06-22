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

# First private subnet from the dev VPC (matches main.tf default layout).
SUBNET="$(aws ec2 describe-subnets \
  --filters "Name=tag:Name,Values=*private*" \
  --query 'Subnets[0].SubnetId' \
  --output text)"

if [[ -z "${SUBNET}" || "${SUBNET}" == "None" ]]; then
  echo "Could not resolve a private subnet. Set SUBNET_ID and re-run." >&2
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
echo "Tail logs:"
LOG_GROUP="$(terraform output -raw ingest_log_group_name)"
echo "  aws logs tail ${LOG_GROUP} --follow"
echo ""
echo "When complete, export JSONL from inside the task or add export to the ECS command."
