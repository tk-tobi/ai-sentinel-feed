#!/usr/bin/env bash
# Bridge AWS CLI `aws login` sessions to tools that need env-based credentials
# (Terraform, some SDK defaults). Safe to source from other scripts.

ensure_aws_credentials() {
  if [[ -n "${AWS_ACCESS_KEY_ID:-}" && -n "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
    return 0
  fi

  if ! command -v aws >/dev/null 2>&1; then
    echo "AWS CLI not found. Install it and run: aws login" >&2
    return 1
  fi

  if aws configure export-credentials --format env >/dev/null 2>&1; then
    # shellcheck disable=SC1090
    eval "$(aws configure export-credentials --format env)"
  fi

  if ! aws sts get-caller-identity >/dev/null 2>&1; then
    cat >&2 <<'EOF'
AWS credentials are not available.

The AWS CLI may be logged in, but Terraform cannot use `aws login` directly.

Fix:
  aws login
  eval "$(aws configure export-credentials --format env)"
  ./infra/scripts/apply.sh dev

Or configure long-lived keys:
  aws configure
EOF
    return 1
  fi
}
