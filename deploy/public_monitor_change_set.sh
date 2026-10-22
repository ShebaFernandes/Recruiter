#!/usr/bin/env bash
# FUTURE APPROVAL ONLY: prepares a new-stack change set; never executes it.
set -euo pipefail
test "${ENTER_APPROVE_MONITOR_CHANGE_SET:-}" = "431988153216/ap-southeast-2" || {
  echo "Approval gate closed; no AWS requests made." >&2
  exit 1
}
test "$#" -eq 2 || { echo "Usage: $0 ARTIFACT_DIRECTORY TEMPLATE_SHA256" >&2; exit 1; }
cd "$1"
test "$(shasum -a 256 template.json | cut -d ' ' -f1)" = "$2"
shasum -a 256 -c SHA256SUMS
region=ap-southeast-2
test "$(aws sts get-caller-identity --region "$region" --query Account --output text)" = \
  "431988153216"
aws cloudformation validate-template --region "$region" --template-body file://template.json
# CREATE fails rather than updating an existing stack. No application/EC2 resources
# occur in this template. Operator must review the complete change set before execution.
aws cloudformation create-change-set --region "$region" \
  --stack-name enter-public-https-monitor --change-set-type CREATE \
  --change-set-name "review-$(date -u +%Y%m%dT%H%M%SZ)" \
  --capabilities CAPABILITY_NAMED_IAM --template-body file://template.json
echo "Change set prepared only. Do not execute without separate approval."
