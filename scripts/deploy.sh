#!/bin/bash
set -euo pipefail

# ============================================================
# Deploy stock pipeline to AWS free-tier EC2 (t2.micro)
#
# Usage:
#   ./scripts/deploy.sh <key-pair-name> <path-to-pem-file> [region]
#
# Example:
#   ./scripts/deploy.sh my-key ~/.ssh/my-key.pem us-east-1
# ============================================================

KEY_PAIR_NAME="${1:-}"
PEM_FILE="${2:-}"
REGION="${3:-us-east-1}"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# ---- Prerequisite Checks ----

echo "========================================="
echo " Checking prerequisites..."
echo "========================================="

MISSING=0

# Check AWS CLI
if ! command -v aws &>/dev/null; then
  echo "  [MISSING] AWS CLI"
  echo "    Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
  echo "    macOS:   brew install awscli"
  MISSING=1
else
  echo "  [OK] AWS CLI $(aws --version 2>&1 | head -1)"
fi

# Check Terraform
if ! command -v terraform &>/dev/null; then
  echo "  [MISSING] Terraform"
  echo "    Install: https://developer.hashicorp.com/terraform/install"
  echo "    macOS:   brew install terraform"
  MISSING=1
else
  echo "  [OK] Terraform $(terraform version -json 2>/dev/null | python3 -c 'import sys,json;print(json.load(sys.stdin)["terraform_version"])' 2>/dev/null || terraform version | head -1)"
fi

# Check AWS credentials
if ! aws sts get-caller-identity &>/dev/null; then
  echo "  [MISSING] AWS credentials not configured"
  echo "    Run:     aws configure"
  echo "    You need: Access Key ID, Secret Access Key, Region"
  echo "    Get keys: AWS Console → IAM → Users → Security credentials → Create access key"
  MISSING=1
else
  ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
  echo "  [OK] AWS credentials (account: $ACCOUNT)"
fi

# Check arguments
if [ -z "$KEY_PAIR_NAME" ] || [ -z "$PEM_FILE" ]; then
  echo ""
  echo "  [MISSING] Key pair name and PEM file required"
  echo ""
  echo "  If you don't have a key pair yet:"
  echo "    1. Go to AWS Console → EC2 → Key Pairs → Create key pair"
  echo "    2. Name it (e.g. 'stock-pipeline'), select .pem format"
  echo "    3. Download the .pem file"
  echo "    4. Run: chmod 400 ~/Downloads/stock-pipeline.pem"
  echo "    5. Re-run: ./scripts/deploy.sh stock-pipeline ~/Downloads/stock-pipeline.pem"
  echo ""
  MISSING=1
elif [ ! -f "$PEM_FILE" ]; then
  echo "  [MISSING] PEM file not found: $PEM_FILE"
  MISSING=1
else
  echo "  [OK] Key pair: $KEY_PAIR_NAME ($PEM_FILE)"
fi

if [ "$MISSING" -eq 1 ]; then
  echo ""
  echo "Fix the above issues and re-run."
  exit 1
fi

echo ""
echo "========================================="
echo " Deploying to AWS ($REGION)"
echo " Instance: t2.micro (free tier)"
echo "========================================="

# ---- Step 1: Terraform ----
echo ""
echo "[1/4] Provisioning EC2 + S3 with Terraform..."
cd "$PROJECT_DIR/terraform"

terraform init -input=false
terraform apply -auto-approve \
  -var="key_pair_name=$KEY_PAIR_NAME" \
  -var="aws_region=$REGION"

EC2_IP=$(terraform output -raw ec2_public_ip)
S3_BUCKET=$(terraform output -raw s3_bucket_name)
echo ""
echo "  EC2:    $EC2_IP"
echo "  S3:     $S3_BUCKET"

# ---- Step 2: Wait for EC2 ----
echo ""
echo "[2/4] Waiting for EC2 to be ready..."

for i in $(seq 1 30); do
  if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i "$PEM_FILE" ec2-user@"$EC2_IP" "echo ok" 2>/dev/null; then
    break
  fi
  echo "  Waiting for SSH... ($i/30)"
  sleep 10
done

echo "  Waiting for Docker install to finish..."
for i in $(seq 1 20); do
  if ssh -o StrictHostKeyChecking=no -i "$PEM_FILE" ec2-user@"$EC2_IP" "docker --version" 2>/dev/null; then
    echo "  Docker ready!"
    break
  fi
  sleep 15
done

# ---- Step 3: Deploy project ----
echo ""
echo "[3/4] Copying project to EC2..."
cd "$PROJECT_DIR"

tar czf /tmp/pipeline-deploy.tar.gz \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='.env' \
  --exclude='terraform/.terraform' \
  --exclude='terraform/*.tfstate*' \
  --exclude='notebooks' \
  -C "$PROJECT_DIR" .

scp -o StrictHostKeyChecking=no -i "$PEM_FILE" /tmp/pipeline-deploy.tar.gz ec2-user@"$EC2_IP":/tmp/
rm /tmp/pipeline-deploy.tar.gz

ssh -o StrictHostKeyChecking=no -i "$PEM_FILE" ec2-user@"$EC2_IP" << 'REMOTE'
  set -e
  mkdir -p ~/pipeline && cd ~/pipeline
  tar xzf /tmp/pipeline-deploy.tar.gz 2>/dev/null
  rm -f /tmp/pipeline-deploy.tar.gz

  [ -f .env ] || cp .env.example .env

  echo "Building custom images..."
  sudo docker build -t pipeline-producer -f Dockerfile.producer . 2>&1 | tail -3
  sudo docker build -t pipeline-dashboard -f Dockerfile.dashboard . 2>&1 | tail -3

  echo "Starting services..."
  sudo docker-compose -f docker-compose.demo.yml up -d 2>&1 | tail -20

  echo ""
  echo "Container status:"
  sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
REMOTE

# ---- Step 4: Done ----
echo ""
echo "[4/4] Deployment complete!"
echo ""
echo "========================================="
echo " YOUR SERVICES (give 2-3 min to warm up)"
echo "========================================="
echo ""
echo "  Grafana:     http://$EC2_IP:3000   (admin / admin)"
echo "  Dashboard:   http://$EC2_IP:8501"
echo "  Prometheus:  http://$EC2_IP:9090"
echo ""
echo "  SSH:  ssh -i $PEM_FILE ec2-user@$EC2_IP"
echo ""
echo "  Check logs:  ssh -i $PEM_FILE ec2-user@$EC2_IP 'cd pipeline && sudo docker-compose -f docker-compose.demo.yml logs -f'"
echo ""
echo " When done taking screenshots, tear down:"
echo "   ./scripts/teardown.sh $KEY_PAIR_NAME $REGION"
echo "========================================="
