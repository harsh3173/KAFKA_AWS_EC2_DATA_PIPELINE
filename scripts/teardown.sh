#!/bin/bash
set -euo pipefail

# ============================================================
# Tear down ALL AWS infrastructure — EC2, S3, IAM, everything.
#
# Usage:
#   ./scripts/teardown.sh <key-pair-name> [region]
# ============================================================

KEY_PAIR_NAME="${1:-dummy}"
REGION="${2:-us-east-1}"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "========================================="
echo " TEARDOWN — Destroying all AWS resources"
echo "========================================="
echo ""
echo " This will permanently destroy:"
echo "   - EC2 instance"
echo "   - S3 bucket and all data"
echo "   - Security groups"
echo "   - IAM roles"
echo ""
read -p " Type 'yes' to confirm: " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
  echo "Aborted."
  exit 0
fi

cd "$PROJECT_DIR/terraform"

# Empty S3 bucket first (terraform can't destroy non-empty buckets)
echo ""
echo "[1/2] Emptying S3 bucket..."
BUCKET=$(terraform output -raw s3_bucket_name 2>/dev/null || echo "")
if [ -n "$BUCKET" ]; then
  # Disable versioning first, then delete all versions
  aws s3api put-bucket-versioning --bucket "$BUCKET" --versioning-configuration Status=Suspended --region "$REGION" 2>/dev/null || true
  aws s3 rm "s3://$BUCKET" --recursive --region "$REGION" 2>/dev/null || true
  # Delete version markers too
  aws s3api list-object-versions --bucket "$BUCKET" --region "$REGION" --output json 2>/dev/null | \
    python3 -c "
import sys,json
data=json.load(sys.stdin)
for key in ['Versions','DeleteMarkers']:
  for obj in data.get(key,[]):
    print(obj['Key'],obj['VersionId'])
" 2>/dev/null | while read KEY VID; do
    aws s3api delete-object --bucket "$BUCKET" --key "$KEY" --version-id "$VID" --region "$REGION" 2>/dev/null || true
  done
  echo "  Bucket emptied."
else
  echo "  No bucket found, skipping."
fi

echo ""
echo "[2/2] Destroying infrastructure..."
terraform destroy -auto-approve \
  -var="key_pair_name=$KEY_PAIR_NAME" \
  -var="aws_region=$REGION"

echo ""
echo "========================================="
echo " Done. All resources destroyed."
echo " No ongoing AWS charges."
echo "========================================="
