# Deployment Decision Guide

**Quick reference: What deployment method should I use?**

---

## 🎯 Decision Flowchart

```
What did you change?
    │
    ├─ Python code (src/, config/, run.py)
    │  └─> Use: Hot Deploy
    │     Command: ./scripts/deploy-hot.sh production
    │     Downtime: 0 seconds
    │     n8n restarts: NO
    │
    ├─ n8n workflow (just tweaking)
    │  └─> Edit in n8n UI
    │     Command: Open https://your-domain.com
    │     Downtime: 0 seconds
    │     Deployment: Not needed
    │
    ├─ n8n workflow (major changes, need version control)
    │  └─> Export → Git → Deploy
    │     Command: ./scripts/deploy-workflows.sh production
    │     Downtime: 0 seconds
    │     n8n restarts: NO
    │
    ├─ Docker/n8n configuration
    │  └─> Use: Standard Deploy
    │     Command: ./scripts/deploy.sh production
    │     Downtime: 5-10 seconds
    │     n8n restarts: YES
    │
    └─ Infrastructure (Terraform, EC2)
       └─> Use: Terraform + Standard Deploy
          Command: terraform apply && ./scripts/deploy.sh
          Downtime: Varies
          n8n restarts: YES
```

---

## 📊 Quick Reference Table

| What Changed | Method | Command | n8n Restart? | Downtime |
|--------------|--------|---------|--------------|----------|
| **Python code** | Hot Deploy | `./scripts/deploy-hot.sh` | ❌ | 0 sec |
| **Config files** | Hot Deploy | `./scripts/deploy-hot.sh` | ❌ | 0 sec |
| **Workflow (quick fix)** | n8n UI | Edit & Save in UI | ❌ | 0 sec |
| **Workflow (version control)** | Workflow Deploy | `./scripts/deploy-workflows.sh` | ❌ | 0 sec |
| **n8n version** | Standard Deploy | `./scripts/deploy.sh` | ✅ | 5-10 sec |
| **Docker config** | Standard Deploy | `./scripts/deploy.sh` | ✅ | 5-10 sec |
| **Infrastructure** | Terraform | `terraform apply` | ✅ | Varies |

---

## 💡 Common Scenarios

### "I updated extraction keywords"
```bash
# Edit config/default_config.json
vim config/default_config.json

# Hot deploy (no n8n restart)
./scripts/deploy-hot.sh production
```
**Downtime:** 0 seconds

---

### "I fixed a bug in the Python extraction logic"
```bash
# Edit src/stage2_verbatim.py
vim src/stage2_verbatim.py

# Hot deploy (no n8n restart)
./scripts/deploy-hot.sh production
```
**Downtime:** 0 seconds

---

### "I want to add email notifications to my n8n workflow"
```bash
# Option A: Quick (UI edit)
# 1. Open n8n UI
# 2. Add "Send Email" node
# 3. Click Save
# Done! (0 downtime)

# Option B: Version controlled
# 1. Edit in UI, test
# 2. Export workflow
# 3. Commit to git
git add n8n/workflows/
git commit -m "feat: Add email notifications"
# 4. Deploy
./scripts/deploy-workflows.sh production
```
**Downtime:** 0 seconds (both options)

---

### "I need to upgrade n8n to latest version"
```bash
# Edit docker-compose.yml or terraform
vim terraform/main.tf  # Update N8N_VERSION

# Standard deploy (n8n will restart)
./scripts/deploy.sh production
```
**Downtime:** 5-10 seconds

---

### "I changed both Python code AND n8n workflow"
```bash
# 1. Hot deploy Python first
./scripts/deploy-hot.sh production

# 2. Deploy workflow separately
./scripts/deploy-workflows.sh production

# OR: Just use standard deploy for both
./scripts/deploy.sh production
```
**Downtime:** 0 seconds (Option 1) or 5-10 seconds (Option 2)

---

## 🚦 Priority Matrix

### Zero Downtime Required?
```
Use: Hot Deploy (Python) or Workflow Deploy (n8n) or UI Edit
Restart n8n: NO
```

### Version Control Required?
```
Python: Hot Deploy + Git
Workflows: Export → Git → Workflow Deploy
```

### Quick Fix Needed?
```
Python: Hot Deploy (~30 sec)
Workflows: Edit in UI (~1 min)
```

### Multiple Changes?
```
If Python + Workflow: Hot Deploy + Workflow Deploy
If touching Docker/infrastructure: Standard Deploy
```

---

## 📋 Deployment Checklist

Before deploying, check:

**For Hot Deploy:**
- [ ] Only changed Python/config files
- [ ] Tested locally
- [ ] No n8n/Docker changes

**For Workflow Deploy:**
- [ ] Exported workflow from UI
- [ ] Committed to git
- [ ] Tested in staging (if available)

**For Standard Deploy:**
- [ ] Made Docker/infrastructure changes
- [ ] Acceptable to have 5-10 sec downtime
- [ ] Notified team (if needed)

---

## 🎯 Best Practices

### Daily Workflow
```bash
# Most common: Python changes
./scripts/deploy-hot.sh production
# 99% of your deployments
```

### Weekly Workflow Updates
```bash
# Update workflows in UI throughout week
# Friday: Export and commit to git
./scripts/deploy-workflows.sh production
```

### Monthly Infrastructure Updates
```bash
# Update n8n version, Docker config, etc.
./scripts/deploy.sh production
# Notify team of 10-second downtime
```

---

## 🔍 Quick Self-Check

**Ask yourself:**

1. **Did I change files in `src/` or `config/`?**
   → Yes: Hot Deploy

2. **Did I edit a workflow in n8n UI?**
   → Small change: Leave it
   → Major change: Export → Git → Deploy

3. **Did I change Docker, n8n settings, or infrastructure?**
   → Yes: Standard Deploy

4. **Am I not sure?**
   → Use Standard Deploy (safest, works for everything)

---

## 🆘 Emergency Rollback

**Python changes:**
```bash
ssh ec2-user@ip
cd /app/backups
sudo tar -xzf $(ls -t hot-backup-* | head -1) -C /
```

**Workflow changes:**
```bash
# Find previous version in git
git log n8n/workflows/
git checkout HEAD~1 n8n/workflows/10k_extraction_workflow.json
./scripts/deploy-workflows.sh production
```

**Everything:**
```bash
ssh ec2-user@ip
cd /app/backups
sudo tar -xzf $(ls -t backup-* | head -1) -C /
cd /opt/n8n && docker compose restart n8n
```

---

## 📚 Full Documentation

- **Hot Deploy:** [HOT_DEPLOYMENT.md](HOT_DEPLOYMENT.md)
- **Workflow Management:** [WORKFLOW_MANAGEMENT.md](WORKFLOW_MANAGEMENT.md)
- **CI/CD Setup:** [CI_CD_SETUP.md](CI_CD_SETUP.md)
- **Quick Start:** [DEPLOYMENT_QUICKSTART.md](DEPLOYMENT_QUICKSTART.md)

---

## ✅ Summary

**Simple rule:**
- Python changes → **Hot Deploy** (0 downtime)
- Workflow tweaks → **n8n UI** (0 downtime)
- Everything else → **Standard Deploy** (5-10 sec downtime)

**When in doubt:** Use standard deploy. It always works.

🚀 **Most deployments will be hot deploys!**
