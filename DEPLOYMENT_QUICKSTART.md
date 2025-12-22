# Deployment Quick Start

Get your CI/CD pipeline running in 15 minutes.

---

## 🔥 Hot Deploy (Zero Downtime) - NEW!

**Updates Python code WITHOUT restarting n8n** - workflows keep running!

```bash
# One command deployment - n8n never stops
./scripts/deploy-hot.sh production
```

✅ 0 seconds downtime
✅ Workflows stay active
✅ Webhooks stay online
✅ 30 second deployment

[Full Hot Deployment Guide →](HOT_DEPLOYMENT.md)

---

## ⚡ Option 1: GitHub Actions (Recommended)

### 1. Push to GitHub (2 min)
```bash
git remote add origin https://github.com/YOUR_USERNAME/ai-tax-evidence-finder.git
git add .
git commit -m "Initial commit with CI/CD"
git push -u origin main
```

### 2. Add Secrets (5 min)
Go to: `Settings → Secrets → Actions → New secret`

Add these **4 required secrets:**
```
AWS_ACCESS_KEY_ID          = your-aws-key
AWS_SECRET_ACCESS_KEY      = your-aws-secret
EC2_SSH_PRIVATE_KEY        = contents of ~/.ssh/your-key.pem
ANTHROPIC_API_KEY          = sk-ant-...
```

### 3. Tag Your EC2 Instance (1 min)
```bash
aws ec2 create-tags \
  --resources i-your-instance-id \
  --tags Key=Name,Value=ai-tax-evidence-finder
```

### 4. Push a Change to Deploy (1 min)
```bash
echo "# Test" >> README.md
git add README.md
git commit -m "test: Deploy"
git push
```

Watch at: https://github.com/YOUR_USERNAME/ai-tax-evidence-finder/actions

**Done!** Every push to `main` now auto-deploys. ✅

---

## ⚡ Option 2: Manual Deployment (Faster Setup)

### 1. Create Config (2 min)
```bash
cp .env.example .env.production
vim .env.production  # Add your EC2_HOST, EC2_KEY_PATH
```

### 2. Deploy (3 min)
```bash
./scripts/deploy.sh production
```

**Done!** Deployed to EC2. ✅

---

## 🔍 Verify Deployment

```bash
# SSH to EC2
ssh -i ~/.ssh/your-key.pem ec2-user@YOUR_EC2_IP

# Test extraction engine
cd /app
python3 run.py --help

# Check n8n
docker logs n8n

# Test extraction (if you have API key)
export ANTHROPIC_API_KEY='sk-ant-...'
python3 run.py extract test.pdf --config config/default_config.json
```

---

## 🎯 What Each Option Does

| Feature | GitHub Actions | Manual Script |
|---------|----------------|---------------|
| Setup time | 10 min | 5 min |
| Auto-deploy on push | ✅ | ❌ |
| Runs tests | ✅ | ✅ |
| Builds Docker | ✅ | ❌ |
| Rollback support | ✅ | ✅ |
| Team access | ✅ | ❌ |

---

## 📚 Full Documentation

- Complete guide: [CI_CD_SETUP.md](CI_CD_SETUP.md)
- Troubleshooting: [CI_CD_SETUP.md#troubleshooting](CI_CD_SETUP.md#troubleshooting)
- Manual deployment: [scripts/deploy.sh](scripts/deploy.sh)

---

## 🐛 Common Issues

**"Can't find EC2 instance"**
→ Add tag: `Key=Name, Value=ai-tax-evidence-finder`

**"SSH connection failed"**
→ Check EC2_SSH_PRIVATE_KEY secret has complete key (including -----BEGIN RSA PRIVATE KEY-----)

**"Tests failed"**
→ Run locally: `python -m pytest tests/` and fix errors

**"n8n not restarting"**
→ SSH to EC2: `cd /opt/n8n && docker compose restart n8n`

---

## 💡 Pro Tips

**Tip 1:** Test locally before pushing
```bash
python -m pytest tests/
./scripts/deploy.sh staging
```

**Tip 2:** Watch deployment live
```bash
# Terminal 1: Watch GitHub Actions
gh run watch

# Terminal 2: Watch EC2 logs
ssh ec2-user@ip "tail -f /var/log/n8n-setup.log"
```

**Tip 3:** Quick rollback
```bash
ssh ec2-user@ip
cd /app/backups
sudo tar -xzf $(ls -t | head -1) -C /
docker compose restart n8n
```

**Ready to deploy!** 🚀
