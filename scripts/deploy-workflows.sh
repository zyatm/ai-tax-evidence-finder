#!/bin/bash
# Deploy n8n workflows without restarting n8n
# Workflows are imported via n8n API

set -e

ENVIRONMENT=${1:-production}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "n8n Workflow Deployment"
echo "Environment: $ENVIRONMENT"
echo "=========================================="

# Load environment
if [ -f "$PROJECT_ROOT/.env.$ENVIRONMENT" ]; then
    source "$PROJECT_ROOT/.env.$ENVIRONMENT"
fi

if [ -z "$EC2_HOST" ]; then
    echo "❌ Error: EC2_HOST not set"
    exit 1
fi

EC2_USER=${EC2_USER:-ec2-user}
EC2_KEY_PATH=${EC2_KEY_PATH:-$HOME/.ssh/id_rsa}
N8N_DOMAIN=${N8N_DOMAIN:-localhost:5678}
N8N_API_KEY=${N8N_API_KEY}

echo ""
echo "Target: $EC2_USER@$EC2_HOST"
echo "n8n: $N8N_DOMAIN"
echo ""

# Check if we have workflows to deploy
WORKFLOW_DIR="$PROJECT_ROOT/n8n/workflows"
if [ ! -d "$WORKFLOW_DIR" ]; then
    echo "❌ No workflow directory found: $WORKFLOW_DIR"
    exit 1
fi

WORKFLOW_COUNT=$(ls -1 "$WORKFLOW_DIR"/*.json 2>/dev/null | wc -l)
if [ "$WORKFLOW_COUNT" -eq 0 ]; then
    echo "⚠️  No workflow files found in $WORKFLOW_DIR"
    exit 0
fi

echo "Found $WORKFLOW_COUNT workflow(s) to deploy"
echo ""

# Upload workflows to EC2
echo "==> Uploading workflows..."
scp -i "$EC2_KEY_PATH" -r "$WORKFLOW_DIR" "$EC2_USER@$EC2_HOST:/tmp/"

# Deploy workflows via n8n API
echo "==> Deploying workflows via n8n API..."
ssh -i "$EC2_KEY_PATH" "$EC2_USER@$EC2_HOST" << 'ENDSSH'
set -e

N8N_URL="http://localhost:5678"
WORKFLOW_DIR="/tmp/workflows"

echo "==> Checking n8n status..."
if ! curl -f "$N8N_URL" > /dev/null 2>&1; then
    echo "❌ n8n is not accessible at $N8N_URL"
    exit 1
fi
echo "✓ n8n is running"

echo ""
echo "==> Importing workflows..."

for workflow_file in "$WORKFLOW_DIR"/*.json; do
    if [ ! -f "$workflow_file" ]; then
        continue
    fi

    workflow_name=$(basename "$workflow_file" .json)
    echo "  • $workflow_name"

    # Import workflow using n8n CLI (inside container)
    docker exec n8n n8n import:workflow --input="$workflow_file" 2>&1 | grep -v "Workflow" || true

    echo "    ✓ Imported"
done

echo ""
echo "==> Activating workflows..."

# Get list of all workflows and activate them
docker exec n8n n8n list:workflow --output=json 2>/dev/null | \
    jq -r '.[] | select(.active == false) | .id' | \
    while read workflow_id; do
        if [ -n "$workflow_id" ]; then
            docker exec n8n n8n update:workflow --id="$workflow_id" --active=true
            echo "  ✓ Activated workflow ID: $workflow_id"
        fi
    done

echo ""
echo "==> Workflow deployment summary..."
docker exec n8n n8n list:workflow

# Cleanup
rm -rf /tmp/workflows

echo ""
echo "✅ Workflow deployment complete!"
echo "   • n8n was NOT restarted"
echo "   • Workflows are active"
ENDSSH

echo ""
echo "=========================================="
echo "Deployment Complete"
echo "=========================================="
echo "Environment: $ENVIRONMENT"
echo "Status: ✅ Success"
echo ""
echo "Next steps:"
echo "  • View workflows: https://$N8N_DOMAIN"
echo "  • Test workflow: Trigger via webhook"
echo "  • Check logs: ssh $EC2_USER@$EC2_HOST 'docker logs -f n8n'"
echo "=========================================="
