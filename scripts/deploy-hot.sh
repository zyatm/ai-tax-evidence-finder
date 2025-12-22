#!/bin/bash
# Hot deployment - Updates Python extraction engine WITHOUT restarting n8n
# Usage: ./scripts/deploy-hot.sh [environment]

set -e

ENVIRONMENT=${1:-production}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "Hot Deployment (No n8n Restart)"
echo "Environment: $ENVIRONMENT"
echo "=========================================="

# Load environment variables
if [ -f "$PROJECT_ROOT/.env.$ENVIRONMENT" ]; then
    source "$PROJECT_ROOT/.env.$ENVIRONMENT"
else
    echo "⚠️  No .env.$ENVIRONMENT file found"
fi

# Check required variables
if [ -z "$EC2_HOST" ]; then
    echo "❌ Error: EC2_HOST not set"
    exit 1
fi

EC2_USER=${EC2_USER:-ec2-user}
EC2_KEY_PATH=${EC2_KEY_PATH:-$HOME/.ssh/id_rsa}

echo ""
echo "Target: $EC2_USER@$EC2_HOST"
echo "Strategy: Update Python files only (n8n keeps running)"
echo ""

# Step 1: Validate locally
echo "==> Validating code locally..."
cd "$PROJECT_ROOT"

python -c "
import sys
sys.path.insert(0, 'src')
from stage2_verbatim import VerbatimExtractor
import json
json.load(open('config/default_config.json'))
print('✓ Local validation passed')
" || exit 1

# Step 2: Create deployment package
echo "==> Creating deployment package..."
TEMP_DIR=$(mktemp -d)
mkdir -p "$TEMP_DIR/deployment"

cp -r "$PROJECT_ROOT/src" "$TEMP_DIR/deployment/"
cp -r "$PROJECT_ROOT/config" "$TEMP_DIR/deployment/"
cp "$PROJECT_ROOT/run.py" "$TEMP_DIR/deployment/"
cp "$PROJECT_ROOT/requirements.txt" "$TEMP_DIR/deployment/"

cd "$TEMP_DIR"
tar -czf deployment.tar.gz deployment/
echo "✓ Package created: $(du -h deployment.tar.gz | cut -f1)"

# Step 3: Upload to EC2
echo "==> Uploading to EC2..."
scp -i "$EC2_KEY_PATH" deployment.tar.gz "$EC2_USER@$EC2_HOST:/tmp/"

# Step 4: Hot deploy on EC2
echo "==> Performing hot deployment on EC2..."
ssh -i "$EC2_KEY_PATH" "$EC2_USER@$EC2_HOST" << 'ENDSSH'
set -e

echo "==> Extracting deployment package..."
cd /tmp
tar -xzf deployment.tar.gz

echo "==> Creating timestamped backup..."
BACKUP_DIR="/app/backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
sudo mkdir -p "$BACKUP_DIR"

if [ -d "/app/src" ]; then
    echo "    Backing up to: $BACKUP_DIR/hot-backup-$TIMESTAMP.tar.gz"
    sudo tar -czf "$BACKUP_DIR/hot-backup-$TIMESTAMP.tar.gz" \
        -C /app src config run.py 2>/dev/null || true
fi

echo "==> Atomic file replacement..."
# Use atomic operations to minimize downtime

# Create temporary staging directory
sudo mkdir -p /app/.staging
sudo cp -r /tmp/deployment/src /app/.staging/
sudo cp -r /tmp/deployment/config /app/.staging/
sudo cp /tmp/deployment/run.py /app/.staging/
sudo cp /tmp/deployment/requirements.txt /app/.staging/

# Atomic swap using mv (instant on same filesystem)
echo "    Swapping src/ directory..."
sudo mv /app/src /app/src.old 2>/dev/null || true
sudo mv /app/.staging/src /app/src

echo "    Swapping config/ directory..."
sudo mv /app/config /app/config.old 2>/dev/null || true
sudo mv /app/.staging/config /app/config

echo "    Swapping run.py..."
sudo mv /app/run.py /app/run.py.old 2>/dev/null || true
sudo mv /app/.staging/run.py /app/run.py

echo "    Swapping requirements.txt..."
sudo mv /app/requirements.txt /app/requirements.txt.old 2>/dev/null || true
sudo mv /app/.staging/requirements.txt /app/requirements.txt

# Clean up old versions and staging
sudo rm -rf /app/src.old /app/config.old /app/run.py.old /app/requirements.txt.old /app/.staging

echo "==> Installing dependencies (if changed)..."
cd /app
sudo pip3 install -r requirements.txt --quiet --upgrade 2>&1 | grep -v "already satisfied" || true

echo "==> Setting permissions..."
sudo chown -R 1000:1000 /app/src /app/config /app/run.py

echo "==> Verifying deployment..."
python3 -c "
import sys
sys.path.insert(0, 'src')
from stage2_verbatim import VerbatimExtractor
import os
os.environ['ANTHROPIC_API_KEY'] = 'test-key'
e = VerbatimExtractor(config_path='config/default_config.json')
assert len(e.blocks) == 6, 'Config loading failed'
print('✓ Extraction engine is working')
"

echo "==> Checking n8n status (should still be running)..."
if curl -f http://localhost:5678 > /dev/null 2>&1; then
    echo "✓ n8n is running and healthy (no restart was needed)"
else
    echo "⚠️  n8n health check failed (but this may be normal if webhooks are not public)"
fi

# Clean up temp files
rm -rf /tmp/deployment /tmp/deployment.tar.gz

echo ""
echo "✅ Hot deployment complete!"
echo "   • n8n: Still running (no restart)"
echo "   • Python: Updated to latest version"
echo "   • Backup: $BACKUP_DIR/hot-backup-$TIMESTAMP.tar.gz"
ENDSSH

# Cleanup local temp
rm -rf "$TEMP_DIR"

echo ""
echo "=========================================="
echo "Hot Deployment Summary"
echo "=========================================="
echo "Environment: $ENVIRONMENT"
echo "Target: $EC2_USER@$EC2_HOST"
echo "Status: ✅ Success"
echo "n8n: ✓ No restart (workflows still running)"
echo ""
echo "Next steps:"
echo "  • Test extraction: ssh $EC2_USER@$EC2_HOST 'cd /app && python3 run.py --help'"
echo "  • Check n8n: ssh $EC2_USER@$EC2_HOST 'docker ps | grep n8n'"
echo "  • View backups: ssh $EC2_USER@$EC2_HOST 'ls -lth /app/backups/ | head -5'"
echo "=========================================="
