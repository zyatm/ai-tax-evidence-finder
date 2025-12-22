# n8n Workflow Management Guide

How to manage and deploy n8n workflow changes without breaking your CI/CD pipeline.

---

## 🎯 Understanding Workflow Storage

### Where Workflows Live

**In n8n container:**
```
/home/node/.n8n/workflows/*.json
```

**In Docker volume (persistent):**
```
/opt/n8n/data/workflows/*.json
```

**In your git repo (optional):**
```
n8n/workflows/*.json
```

**Key insight:** Workflows are stored in Docker volume, not in your codebase by default.

---

## 🔄 Three Workflow Management Strategies

### **Strategy 1: UI-Only (No Version Control)** 👤 SIMPLEST

**Workflow:**
1. Edit workflows in n8n web UI
2. Click "Save"
3. Done - changes are immediate

**Pros:**
- ✅ Zero deployment needed
- ✅ Instant changes
- ✅ Visual editor
- ✅ Easy testing

**Cons:**
- ❌ No version control
- ❌ No audit trail
- ❌ Can't reproduce in other environments
- ❌ No rollback capability

**Best for:**
- Small teams
- Single environment
- Rapid prototyping
- Non-critical workflows

---

### **Strategy 2: Hybrid (Version Control + UI Edits)** ⭐ RECOMMENDED

**Workflow:**
1. Make major changes in git → Deploy
2. Make minor tweaks in UI → Instant
3. Periodically export UI changes back to git

**Process:**

#### A. Export Workflow from n8n
```bash
# In n8n UI:
# 1. Open workflow
# 2. Click "..." menu → "Download"
# 3. Save to n8n/workflows/10k_extraction_workflow.json

# Or via CLI:
ssh ec2-user@your-ec2 \
  "docker exec n8n n8n export:workflow --all --output=/tmp/workflows"

# Copy back to local
scp -r ec2-user@your-ec2:/tmp/workflows n8n/
```

#### B. Commit to Git
```bash
git add n8n/workflows/
git commit -m "feat: Update 10-K extraction workflow - Add error handling"
git push
```

#### C. Deploy Workflows
```bash
# Deploy workflows only (no n8n restart)
./scripts/deploy-workflows.sh production
```

**Pros:**
- ✅ Version control for major changes
- ✅ Quick UI edits for minor tweaks
- ✅ Best of both worlds
- ✅ Rollback capability

**Cons:**
- ⚠️ Need to remember to export changes
- ⚠️ Potential drift between git and live

**Best for:**
- Most teams
- Multiple environments
- Production systems

---

### **Strategy 3: Git-First (Infrastructure as Code)** 🏗️ ENTERPRISE

**Workflow:**
1. All changes in git (edit JSON directly or use n8n CLI)
2. Deploy via CI/CD
3. Never edit in UI

**Setup:**

Create workflow in n8n, export to git:
```bash
# Export all workflows
docker exec n8n n8n export:workflow --all \
  --output=/home/node/.n8n/workflows-export/

# Copy to project
cp /opt/n8n/data/workflows-export/* n8n/workflows/

# Commit
git add n8n/workflows/
git commit -m "chore: Initial workflow export"
```

**Deployment via CI/CD:**
```yaml
# .github/workflows/deploy-workflows.yml
on:
  push:
    paths:
      - 'n8n/workflows/**'

jobs:
  deploy-workflows:
    steps:
      - name: Import workflows to n8n
        run: |
          for workflow in n8n/workflows/*.json; do
            docker exec n8n n8n import:workflow --input="$workflow"
          done
```

**Pros:**
- ✅ Full version control
- ✅ Audit trail
- ✅ Reproducible
- ✅ Multi-environment support
- ✅ Automated deployment

**Cons:**
- ❌ No visual editing (edit JSON)
- ❌ Slower iteration
- ❌ More setup

**Best for:**
- Large teams
- Regulated industries
- Multiple environments (dev/staging/prod)

---

## 📋 Quick Reference: What Needs Restarting?

| Change Type | Hot Deploy | Workflow Deploy | n8n Restart | Downtime |
|-------------|-----------|----------------|-------------|----------|
| Python code (`src/`) | ✅ | ❌ | ❌ | 0 sec |
| Config files (`config/`) | ✅ | ❌ | ❌ | 0 sec |
| Workflow logic (in UI) | ❌ | ❌ | ❌ | 0 sec |
| Workflow JSON (in git) | ❌ | ✅ | ❌ | 0 sec |
| n8n version | ❌ | ❌ | ✅ | 5-10 sec |
| Docker config | ❌ | ❌ | ✅ | 5-10 sec |
| n8n environment vars | ❌ | ❌ | ✅ | 5-10 sec |

---

## 🚀 Deploying Workflow Changes

### Option 1: Deploy via Script (No Restart)
```bash
# Export workflow from n8n UI first
# Then:
./scripts/deploy-workflows.sh production
```

**What it does:**
1. Uploads workflow JSON files to EC2
2. Imports into n8n via CLI (`n8n import:workflow`)
3. Activates workflows
4. n8n never restarts

**Time:** ~20 seconds
**Downtime:** 0 seconds

---

### Option 2: Deploy via n8n API (No Restart)
```bash
# Using n8n API
curl -X POST https://your-domain.com/api/v1/workflows \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d @n8n/workflows/10k_extraction_workflow.json
```

**Requires:** n8n API key configured

---

### Option 3: Edit in UI (Instant)
```bash
# No deployment needed!
# Just save in UI
```

---

## 🔄 Workflow Backup Strategy

### Automatic Backups

Add to cron on EC2:
```bash
# Backup workflows daily
0 2 * * * docker exec n8n n8n export:workflow --all \
  --output=/home/node/.n8n/backups/workflows-$(date +\%Y\%m\%d).json
```

### Manual Backup
```bash
# SSH to EC2
ssh ec2-user@your-ec2

# Export all workflows
docker exec n8n n8n export:workflow --all \
  --output=/tmp/workflow-backup-$(date +%Y%m%d).json

# Download locally
scp ec2-user@your-ec2:/tmp/workflow-backup-*.json backups/
```

---

## 🎛️ Workflow Development Workflow (Recommended)

### 1. Development Phase
```bash
# Work in n8n UI
# Make changes, test, iterate
# Save frequently
```

### 2. Export to Git
```bash
# When happy with changes:
# In n8n UI: Download workflow

# Move to git
mv ~/Downloads/10k_extraction_workflow.json n8n/workflows/

# Commit
git add n8n/workflows/
git commit -m "feat: Add email notifications to extraction workflow"
git push
```

### 3. Deploy to Staging
```bash
# Test in staging first
./scripts/deploy-workflows.sh staging

# Test thoroughly
```

### 4. Deploy to Production
```bash
# When confident:
./scripts/deploy-workflows.sh production

# Monitor for 5 minutes
```

---

## 🧪 Testing Workflow Changes

### Local Testing (n8n Desktop)
```bash
# Install n8n locally
npm install -g n8n

# Run locally
n8n start

# Import workflow
n8n import:workflow --input=n8n/workflows/10k_extraction_workflow.json

# Test in local UI
open http://localhost:5678
```

### Staging Environment Testing
```bash
# Deploy to staging
./scripts/deploy-workflows.sh staging

# Trigger test workflow
curl -X POST https://staging.your-domain.com/webhook/test-10k \
  -F "file=@test.pdf"

# Check results
```

---

## 🔧 Advanced: Environment-Specific Workflows

### Problem
Need different workflows for dev/staging/prod (different webhooks, different configs).

### Solution: Template Workflows

**1. Create template:**
```json
// n8n/workflows/10k_extraction_workflow.template.json
{
  "nodes": [
    {
      "parameters": {
        "path": "{{WEBHOOK_PATH}}"
      },
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook"
    },
    {
      "parameters": {
        "command": "python3 /app/run.py extract {{$json.filepath}} --config {{CONFIG_PATH}}"
      },
      "name": "Run Extraction",
      "type": "n8n-nodes-base.executeCommand"
    }
  ]
}
```

**2. Generate environment-specific versions:**
```bash
#!/bin/bash
# scripts/generate-workflows.sh

for env in staging production; do
    if [ "$env" = "staging" ]; then
        WEBHOOK_PATH="/webhook/staging-10k"
        CONFIG_PATH="/app/config/staging_config.json"
    else
        WEBHOOK_PATH="/webhook/extract-10k"
        CONFIG_PATH="/app/config/default_config.json"
    fi

    cat n8n/workflows/10k_extraction_workflow.template.json | \
        sed "s|{{WEBHOOK_PATH}}|$WEBHOOK_PATH|g" | \
        sed "s|{{CONFIG_PATH}}|$CONFIG_PATH|g" \
        > "n8n/workflows/10k_extraction_workflow.$env.json"
done
```

**3. Deploy environment-specific workflow:**
```bash
./scripts/generate-workflows.sh
./scripts/deploy-workflows.sh production
```

---

## 🐛 Troubleshooting

### Workflow doesn't update after deployment

**Problem:** n8n caches workflows in memory

**Solution:**
```bash
# Option 1: Deactivate and reactivate
# In n8n UI: Toggle workflow off → on

# Option 2: Reimport with force
docker exec n8n n8n import:workflow \
  --input=/path/to/workflow.json \
  --separate

# Option 3: Restart n8n (last resort)
docker compose restart n8n
```

---

### Workflow import fails

**Problem:** Invalid JSON or missing credentials

**Solution:**
```bash
# Validate JSON
python -m json.tool n8n/workflows/10k_extraction_workflow.json

# Check for credential IDs in workflow
grep -i "credentials" n8n/workflows/10k_extraction_workflow.json

# Credentials need to be set up manually in n8n UI first
```

---

### Workflow exists but won't activate

**Problem:** Missing credentials or nodes

**Solution:**
```bash
# List credentials
docker exec n8n n8n list:credentials

# Check n8n logs for missing nodes
docker logs n8n | grep -i error
```

---

## 💡 Best Practices

### 1. Descriptive Workflow Names
```
✅ 10k_extraction_v2.json
✅ email_notification_workflow.json
❌ workflow1.json
❌ test.json
```

### 2. Version Your Workflows
```bash
# In workflow name or description
"name": "10-K Extraction Pipeline v2.1"
"description": "Updated 2025-01-22 - Added error handling"
```

### 3. Document Changes
```bash
git commit -m "feat(workflow): Add Slack notification on extraction complete

- Added Slack node after extraction
- Sends success/failure status
- Includes file name and evidence count
- Refs: #123"
```

### 4. Test Before Production
```bash
# Always test in staging
./scripts/deploy-workflows.sh staging
# Run test
# Then deploy to prod
./scripts/deploy-workflows.sh production
```

### 5. Keep Backup
```bash
# Before major changes
docker exec n8n n8n export:workflow --all \
  --output=/tmp/backup-before-changes.json
```

---

## 📊 Workflow Change Checklist

Before deploying workflow changes:

- [ ] Tested in n8n UI
- [ ] Exported to `n8n/workflows/`
- [ ] Committed to git with descriptive message
- [ ] Deployed to staging (if you have it)
- [ ] Tested in staging
- [ ] Backed up current production workflow
- [ ] Deployed to production
- [ ] Monitored for 5 minutes after deployment
- [ ] Verified workflow is active
- [ ] Tested one execution

---

## 🎯 Quick Commands

```bash
# Export all workflows from EC2
ssh ec2-user@ip "docker exec n8n n8n export:workflow --all --output=/tmp/workflows"
scp -r ec2-user@ip:/tmp/workflows n8n/

# Deploy workflows to EC2
./scripts/deploy-workflows.sh production

# List active workflows
ssh ec2-user@ip "docker exec n8n n8n list:workflow"

# Activate workflow by ID
ssh ec2-user@ip "docker exec n8n n8n update:workflow --id=1 --active=true"

# Backup workflows
ssh ec2-user@ip "docker exec n8n n8n export:workflow --all --output=/home/node/.n8n/backups/backup-$(date +%Y%m%d).json"
```

---

## 📚 Related Documentation

- **Hot Deployment:** [HOT_DEPLOYMENT.md](HOT_DEPLOYMENT.md) - For Python code changes
- **CI/CD Setup:** [CI_CD_SETUP.md](CI_CD_SETUP.md) - For infrastructure changes
- **n8n Documentation:** https://docs.n8n.io/workflows/import-export/

---

## ✅ Summary

**For workflow changes:**

| Scenario | Method | Restart Needed | Downtime |
|----------|--------|----------------|----------|
| Quick tweak | Edit in UI | ❌ | 0 sec |
| Small change | Edit in UI, export later | ❌ | 0 sec |
| Major change | Git → Deploy script | ❌ | 0 sec |
| New workflow | Create in UI → Export → Git | ❌ | 0 sec |

**Recommended approach:**
1. **Develop** in n8n UI (fast iteration)
2. **Export** to git when stable
3. **Deploy** via script (version controlled)
4. **Monitor** after deployment

🔄 **Workflows can be updated without any downtime!**
