# CI/CD Setup Guide

Complete guide for setting up continuous integration and deployment for the AI Tax Evidence Finder.

---

## 🎯 Overview

**Pipeline:** GitHub Actions → AWS ECR → EC2
**Cost:** Free (GitHub Actions: 2000 min/month for private repos)
**Deployment:** Automatic on push to `main` branch

### What Gets Deployed

1. **Test** → Lint code, validate configs, run unit tests
2. **Build** → Create Docker image, push to registry
3. **Deploy** → Update EC2 instance, restart n8n, run smoke tests

---

## 📋 Prerequisites

- [ ] GitHub repository created
- [ ] AWS account with EC2 instance running
- [ ] SSH access to EC2 instance
- [ ] Anthropic API key

---

## 🚀 Setup Instructions

### Step 1: Initialize Git Repository (2 minutes)

```bash
cd /Users/zaid/Projects/ai-tax-evidence-finder

# Initialize git (if not already done)
git init

# Add remote
git remote add origin https://github.com/YOUR_USERNAME/ai-tax-evidence-finder.git

# Create .gitignore
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
*.egg-info/
dist/
build/

# Environment files
.env
.env.*
!.env.example

# IDE
.vscode/
.idea/
*.swp
.DS_Store

# Test data
*.pdf
*.xlsx
!docs/*.pdf

# Terraform
terraform/*.tfstate*
terraform/.terraform/
*.tfvars
!terraform/*.tfvars.example

# Logs
*.log

# Backups
backups/
EOF

# Commit
git add .
git commit -m "feat: Add CI/CD pipeline with GitHub Actions

- Added GitHub Actions workflow for testing, building, and deployment
- Updated Dockerfile to support new project structure
- Added deployment scripts for manual deployment
- Configured AWS integration for EC2 deployment"

git push -u origin main
```

---

### Step 2: Configure GitHub Secrets (5 minutes)

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add these secrets:

#### Required Secrets

| Secret Name | Value | Where to Get It |
|------------|-------|-----------------|
| `AWS_ACCESS_KEY_ID` | Your AWS access key | AWS Console → IAM → Users → Security credentials |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key | Same as above |
| `EC2_SSH_PRIVATE_KEY` | Your EC2 SSH private key | `cat ~/.ssh/your-key.pem` |
| `ANTHROPIC_API_KEY` | Your Anthropic API key | https://console.anthropic.com/ |

#### Optional Secrets (for Docker Hub)

| Secret Name | Value | Where to Get It |
|------------|-------|-----------------|
| `DOCKER_USERNAME` | Your Docker Hub username | https://hub.docker.com/ |
| `DOCKER_PASSWORD` | Your Docker Hub token | Docker Hub → Account Settings → Security |

**How to add secrets:**
```
1. Go to: https://github.com/YOUR_USERNAME/ai-tax-evidence-finder/settings/secrets/actions
2. Click "New repository secret"
3. Name: AWS_ACCESS_KEY_ID
4. Secret: paste your AWS access key
5. Click "Add secret"
6. Repeat for other secrets
```

---

### Step 3: Verify EC2 Instance Tags (2 minutes)

The CI/CD pipeline finds your EC2 instance by tag. Ensure your instance has:

```bash
# Check current tags
aws ec2 describe-instances \
  --instance-ids i-your-instance-id \
  --query 'Reservations[*].Instances[*].Tags'

# Add tag if missing
aws ec2 create-tags \
  --resources i-your-instance-id \
  --tags Key=Name,Value=ai-tax-evidence-finder
```

---

### Step 4: Test the Pipeline (5 minutes)

#### Automatic Trigger (Recommended)

```bash
# Make a change
echo "# Test" >> README.md

# Commit and push
git add README.md
git commit -m "test: Trigger CI/CD pipeline"
git push

# Watch the pipeline
# Go to: https://github.com/YOUR_USERNAME/ai-tax-evidence-finder/actions
```

#### Manual Deployment (Fallback)

```bash
# Copy environment template
cp .env.example .env.production

# Edit with your values
vim .env.production

# Run deployment
./scripts/deploy.sh production
```

---

## 🔄 CI/CD Workflow

### Trigger Conditions

| Event | Trigger | Actions |
|-------|---------|---------|
| Push to `main` | Automatic | Test → Build → Deploy |
| Push to `develop` | Automatic | Test → Build (no deploy) |
| Pull Request | Automatic | Test only |
| Release published | Automatic | Test → Build → Deploy with version tag |
| Commit message contains `[terraform]` | Automatic | Terraform apply |

### Pipeline Stages

```
┌─────────────────────────────────────────────────────────┐
│  1. TEST STAGE (3-5 minutes)                           │
│  • Lint Python code with flake8                        │
│  • Check code formatting with black                    │
│  • Validate config JSON files                          │
│  • Test config loading                                 │
│  • Run unit tests (if present)                         │
└─────────────────┬───────────────────────────────────────┘
                  ↓ (only if tests pass)
┌─────────────────────────────────────────────────────────┐
│  2. BUILD STAGE (2-4 minutes)                          │
│  • Build Docker image                                   │
│  • Tag with branch name and commit SHA                  │
│  • Push to Docker Hub / AWS ECR                         │
│  • Cache layers for faster builds                       │
└─────────────────┬───────────────────────────────────────┘
                  ↓ (only on main branch)
┌─────────────────────────────────────────────────────────┐
│  3. DEPLOY STAGE (2-3 minutes)                         │
│  • Find EC2 instance by tag                             │
│  • SSH to instance                                      │
│  • Backup current version                               │
│  • Copy new code                                        │
│  • Install dependencies                                 │
│  • Restart n8n                                          │
│  • Run smoke tests                                      │
└─────────────────────────────────────────────────────────┘
```

**Total time:** ~7-12 minutes from push to deployed

---

## 📊 Monitoring Deployments

### View Pipeline Status

**GitHub UI:**
```
https://github.com/YOUR_USERNAME/ai-tax-evidence-finder/actions
```

**Badge in README:**
```markdown
![CI/CD](https://github.com/YOUR_USERNAME/ai-tax-evidence-finder/workflows/CI%2FCD%20Pipeline/badge.svg)
```

### Check Deployment Logs

```bash
# Connect to EC2
ssh -i ~/.ssh/your-key.pem ec2-user@your-ec2-ip

# View n8n logs
docker logs -f n8n

# Check extraction engine
cd /app
python3 run.py --help

# View recent deployments
ls -lt /app/backups/
```

---

## 🔧 Manual Deployment (Bypass CI/CD)

If GitHub Actions is down or you need to deploy immediately:

```bash
# Quick deployment
./scripts/deploy.sh production

# What it does:
# 1. Runs tests locally
# 2. Creates deployment package
# 3. Uploads to EC2 via SCP
# 4. Installs on EC2
# 5. Restarts services
# 6. Runs smoke tests
```

---

## 🔄 Rollback Strategy

### Automatic Rollback (Recommended)

If deployment fails, the pipeline stops and doesn't apply changes.

### Manual Rollback

```bash
# SSH to EC2
ssh -i ~/.ssh/your-key.pem ec2-user@your-ec2-ip

# List backups
cd /app/backups
ls -lt

# Restore backup
sudo tar -xzf backup-20250122-143022.tar.gz -C /

# Restart n8n
cd /opt/n8n
docker compose restart n8n
```

---

## 🐛 Troubleshooting

### Pipeline Fails at Test Stage

**Problem:** Flake8 errors
```
Solution: Run locally first
flake8 src/ --max-line-length=120
black src/ run.py
git add . && git commit -m "fix: Lint errors" && git push
```

**Problem:** Config validation fails
```
Solution: Validate JSON
python -m json.tool config/default_config.json
```

### Pipeline Fails at Build Stage

**Problem:** Docker Hub authentication fails
```
Solution: Check DOCKER_USERNAME and DOCKER_PASSWORD secrets
Or: Remove Docker Hub push (ECR only)
```

**Problem:** AWS ECR authentication fails
```
Solution: Check AWS credentials have ECR permissions
Required policy: AmazonEC2ContainerRegistryPowerUser
```

### Pipeline Fails at Deploy Stage

**Problem:** Can't find EC2 instance
```
Solution: Check EC2 instance has tag Name=ai-tax-evidence-finder
aws ec2 describe-instances --filters "Name=tag:Name,Values=ai-tax-evidence-finder"
```

**Problem:** SSH connection fails
```
Solution: Check EC2_SSH_PRIVATE_KEY secret is correct
Test manually: ssh -i ~/.ssh/key.pem ec2-user@ip
```

**Problem:** n8n doesn't restart
```
Solution: SSH to EC2 and check manually
ssh ec2-user@ip
cd /opt/n8n
docker compose ps
docker compose logs n8n
```

---

## 🔐 Security Best Practices

### Secrets Management

✅ **DO:**
- Store secrets in GitHub Secrets (encrypted at rest)
- Use different API keys for staging/production
- Rotate SSH keys periodically
- Use IAM roles with least privilege

❌ **DON'T:**
- Commit secrets to git (use .gitignore)
- Share secrets in plain text
- Use root AWS credentials
- Reuse SSH keys across projects

### SSH Hardening

```bash
# On EC2 instance
# Disable password authentication
sudo sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart sshd

# Use GitHub Deploy Keys (read-only) instead of personal SSH keys
```

---

## 📈 Advanced Features

### Multi-Environment Deployment

Create separate workflows for staging and production:

```yaml
# .github/workflows/deploy-staging.yml
on:
  push:
    branches: [develop]

# .github/workflows/deploy-production.yml
on:
  push:
    branches: [main]
```

### Blue-Green Deployment

Deploy to a second EC2 instance, test, then swap:

```bash
# Deploy to staging instance
./scripts/deploy.sh staging

# Run integration tests
./scripts/test-staging.sh

# Swap production → staging
# (update load balancer or DNS)
```

### Automated Testing with Real PDFs

```yaml
# Add to .github/workflows/ci-cd.yml
- name: Integration test
  run: |
    python run.py extract tests/fixtures/sample_10k.pdf
    # Verify output contains expected evidence
```

---

## 💰 Cost Optimization

### GitHub Actions Minutes

- **Free tier:** 2000 minutes/month (private repos)
- **Current usage:** ~10 min/deployment
- **Capacity:** ~200 deployments/month

**How to reduce:**
- Cache Docker layers (already implemented)
- Skip redundant steps
- Use `paths:` filters to only run on relevant changes

```yaml
on:
  push:
    paths:
      - 'src/**'
      - 'config/**'
      - 'run.py'
```

### AWS Costs

**Current setup:** Single EC2 t3.small
- **Cost:** ~$15/month
- **ECR storage:** ~$1/month for Docker images

**Optimization:**
- Use spot instances for staging
- Auto-stop staging during off-hours
- Compress Docker images

---

## 📚 Next Steps

1. **Add unit tests:** Create `tests/` directory with pytest
2. **Set up staging environment:** Deploy to separate EC2 for testing
3. **Add Slack notifications:** Get alerts on deployment success/failure
4. **Implement canary deployments:** Gradual rollout to minimize risk
5. **Add performance monitoring:** Track extraction time, costs, errors

---

## 📞 Support

**Issues:** https://github.com/YOUR_USERNAME/ai-tax-evidence-finder/issues
**Actions Logs:** https://github.com/YOUR_USERNAME/ai-tax-evidence-finder/actions
**AWS Console:** https://console.aws.amazon.com/

---

## ✅ Checklist

Before going live:

- [ ] All GitHub secrets configured
- [ ] EC2 instance tagged correctly
- [ ] SSH access working
- [ ] Test deployment successful
- [ ] n8n accessible after deployment
- [ ] Extraction engine tested
- [ ] Backup strategy verified
- [ ] Rollback tested
- [ ] Team trained on deployment process
- [ ] Monitoring configured

**Ready to deploy!** 🚀
