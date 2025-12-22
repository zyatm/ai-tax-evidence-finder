# Hot Deployment Guide

Deploy updates **without restarting n8n** - keep your workflows running during deployments.

---

## 🎯 Why Hot Deployment?

### The Problem
Standard deployment restarts n8n, which means:
- ❌ Active workflows get interrupted
- ❌ Webhook triggers go offline
- ❌ Scheduled workflows may miss executions
- ❌ Users see downtime (5-10 seconds)

### The Solution
Hot deployment updates **only the Python extraction engine** while n8n keeps running:
- ✅ n8n never restarts
- ✅ Workflows keep executing
- ✅ Webhooks stay online
- ✅ Zero downtime
- ✅ Atomic file swaps (no partial updates)

---

## ⚡ How It Works

```
┌─────────────────────────────────────────────────────────┐
│  n8n Running                                            │
│  • Executing workflows                                  │
│  • Listening for webhooks                               │
│  • Scheduled tasks active                               │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Hot Deployment Process                                 │
│  1. Upload new Python files to /tmp                     │
│  2. Backup current version                              │
│  3. Atomic swap: mv old → mv new (instant)              │
│  4. Update Python dependencies                          │
│  5. Verify new version works                            │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  n8n Still Running                                      │
│  • Workflows never stopped                              │
│  • Next extraction uses new code                        │
│  • Webhooks stayed online                               │
└─────────────────────────────────────────────────────────┘
```

**Key insight:** n8n calls Python as an external process via `Execute Command` node. Updating Python files doesn't require n8n restart.

---

## 🚀 Usage

### Option 1: Manual Hot Deploy
```bash
# Configure (once)
cp .env.example .env.production
vim .env.production  # Set EC2_HOST, EC2_KEY_PATH

# Deploy (anytime)
./scripts/deploy-hot.sh production
```

### Option 2: Automatic Hot Deploy (GitHub Actions)
```bash
# Push changes to Python/config files
git add src/ config/ run.py
git commit -m "feat: Update extraction keywords"
git push

# Triggers hot deployment automatically
# Watch: https://github.com/YOUR_USERNAME/ai-tax-evidence-finder/actions
```

---

## 📊 Comparison

| Feature | Hot Deploy | Standard Deploy |
|---------|------------|-----------------|
| **n8n downtime** | 0 seconds | 5-10 seconds |
| **Workflows interrupted** | No | Yes |
| **Webhooks offline** | No | Yes (briefly) |
| **Deployment time** | ~30 seconds | ~2 minutes |
| **Risk** | Very low | Low |
| **Rollback** | Instant | Fast |
| **When to use** | Python/config changes | n8n/infrastructure changes |

---

## 📝 What Gets Updated

### Hot Deploy Updates:
✅ Python source code (`src/**`)
✅ Configuration files (`config/**`)
✅ Main script (`run.py`)
✅ Python dependencies (`requirements.txt`)

### Hot Deploy Does NOT Update:
❌ n8n workflows (`n8n/**`)
❌ n8n version
❌ Docker containers
❌ System packages
❌ Terraform infrastructure

**Rule:** If it's Python-only, use hot deploy. If it touches n8n, use standard deploy.

---

## 🔄 Deployment Strategies

### Strategy 1: Always Hot Deploy (Recommended)
```bash
# Default to hot deployment
./scripts/deploy-hot.sh production
```

**When to use:** 99% of the time (Python changes)

**GitHub Actions:** Automatically uses hot deploy when you push changes to:
- `src/**`
- `config/**`
- `run.py`
- `requirements.txt`

---

### Strategy 2: Mixed Deployment
```bash
# Hot deploy for Python changes
git push  # Auto hot-deploys

# Standard deploy for n8n changes
./scripts/deploy.sh production
```

**When to use:**
- Hot: Updating prompts, keywords, logic
- Standard: Updating n8n workflows, Docker images

---

### Strategy 3: Blue-Green Hot Deploy
```bash
# Deploy to staging first (hot)
./scripts/deploy-hot.sh staging

# Test it
ssh staging-server 'cd /app && python3 run.py extract test.pdf'

# Deploy to production (hot)
./scripts/deploy-hot.sh production
```

**When to use:** High-risk changes that need testing

---

## 🔍 Verification

### Check Deployment Success
```bash
# SSH to EC2
ssh -i ~/.ssh/your-key.pem ec2-user@YOUR_EC2_IP

# Test extraction engine
cd /app
python3 run.py --help

# Check n8n uptime (should be high, not just restarted)
docker ps | grep n8n

# View backup created
ls -lh /app/backups/ | head -5

# Test with real PDF (if you have one)
python3 run.py extract sample.pdf --config config/default_config.json
```

### Expected Output
```
✓ Extraction engine is working
✓ n8n is still running (no restart)
✓ Backup created: /app/backups/hot-backup-20250122-143022.tar.gz
```

---

## ⚙️ How Atomic Swaps Work

### Traditional Approach (Has Race Conditions)
```bash
# ❌ BAD: Files update one-by-one
sudo rm -rf /app/src          # Old code deleted
sudo cp -r new/src /app/src   # New code copied
# ⚠️  If extraction runs between these, it fails!
```

### Atomic Approach (Zero Risk)
```bash
# ✅ GOOD: Instant swap
sudo mv /app/src /app/src.old       # Step 1: Rename old
sudo mv /app/.staging/src /app/src  # Step 2: Rename new
# Both operations are atomic (instant)
# No extraction can run between them
```

**Result:** Extractions always see either complete old version or complete new version. Never a partial state.

---

## 🐛 Troubleshooting

### Problem: Deployment succeeds but old code still running

**Cause:** n8n might have cached the Python process

**Solution:**
```bash
# Option A: Kill any running Python processes (they'll restart automatically)
ssh ec2-user@ip "sudo pkill -f 'python.*run.py' || true"

# Option B: If that doesn't work, restart n8n (quick)
ssh ec2-user@ip "cd /opt/n8n && docker compose restart n8n"
```

---

### Problem: New code breaks something

**Solution 1: Instant rollback**
```bash
ssh ec2-user@ip
cd /app/backups
ls -lt | head -5  # Find latest backup

# Restore (instant)
sudo tar -xzf hot-backup-TIMESTAMP.tar.gz -C /
```

**Solution 2: Roll forward (fix and redeploy)**
```bash
# Fix the issue locally
vim src/stage2_verbatim.py

# Redeploy (hot)
./scripts/deploy-hot.sh production
```

---

### Problem: Dependencies fail to install

**Cause:** Conflicting Python packages

**Solution:**
```bash
# SSH to EC2
ssh ec2-user@ip

# Reinstall clean
sudo pip3 uninstall -r /app/requirements.txt -y
sudo pip3 install -r /app/requirements.txt

# Or: Use virtual environment (better isolation)
cd /app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 🔒 Safety Features

### 1. Backup Before Deploy
Every hot deployment creates a timestamped backup:
```
/app/backups/hot-backup-20250122-143022.tar.gz
```

### 2. Atomic Operations
File swaps are instant (single filesystem operation). No race conditions.

### 3. Verification Step
Deployment fails if new code doesn't load:
```python
# This runs after deployment
from stage2_verbatim import VerbatimExtractor
e = VerbatimExtractor(config_path='config/default_config.json')
assert len(e.blocks) == 6
```

### 4. Old Files Kept Temporarily
Old files moved to `.old` suffix, not deleted immediately:
```
/app/src.old
/app/config.old
```

Can be restored instantly if needed.

---

## 💡 Best Practices

### 1. Test Locally First
```bash
# Before hot deploying
cd /Users/zaid/Projects/ai-tax-evidence-finder
python run.py extract sample.pdf --config config/default_config.json
```

### 2. Deploy Off-Peak Hours
Even though hot deploy has zero downtime, deploy when traffic is lowest for extra safety.

### 3. Monitor After Deploy
```bash
# Watch logs for 5 minutes
ssh ec2-user@ip "docker logs -f n8n"

# Check for errors
ssh ec2-user@ip "cd /app && tail -f *.log"
```

### 4. Keep Backup History
```bash
# Automatically keep last 10 backups
ssh ec2-user@ip "cd /app/backups && ls -t | tail -n +11 | xargs rm -f"
```

---

## 🎛️ Advanced: Canary Deployment

Deploy to one extraction at a time:

```bash
# Deploy to EC2 instance 1
./scripts/deploy-hot.sh production --host ec2-1

# Wait 10 minutes, monitor for errors

# If good, deploy to remaining instances
./scripts/deploy-hot.sh production --host ec2-2
./scripts/deploy-hot.sh production --host ec2-3
```

---

## 📈 Performance Impact

### Deployment Speed
- **Standard deploy:** ~2 minutes (includes n8n restart)
- **Hot deploy:** ~30 seconds (no restart)

### Downtime
- **Standard deploy:** 5-10 seconds (n8n restart)
- **Hot deploy:** 0 seconds (no restart)

### Resource Usage During Deploy
- **CPU:** Minimal spike during file copy
- **Memory:** No change
- **Disk I/O:** Brief spike during tar extraction
- **Network:** Negligible (small Python files)

---

## ✅ When to Use Each Deployment Type

### Use Hot Deploy For:
✅ Updating prompts in `config/`
✅ Adding keywords
✅ Changing extraction logic in `src/`
✅ Updating `run.py`
✅ Minor Python dependency updates

### Use Standard Deploy For:
🔄 Updating n8n workflows
🔄 Changing n8n configuration
🔄 Updating Docker images
🔄 Infrastructure changes (Terraform)
🔄 Major Python version upgrades

---

## 🚀 Quick Reference

```bash
# Hot deploy (manual)
./scripts/deploy-hot.sh production

# Hot deploy (auto via GitHub)
git push origin main  # Only if src/ config/ run.py changed

# Verify deployment
ssh ec2-user@ip 'cd /app && python3 run.py --help'

# Check n8n didn't restart
ssh ec2-user@ip 'docker ps | grep n8n'  # Uptime should be high

# Rollback instantly
ssh ec2-user@ip 'cd /app/backups && sudo tar -xzf $(ls -t | head -1) -C /'
```

---

## 📞 Support

- **Hot deploy script:** [scripts/deploy-hot.sh](scripts/deploy-hot.sh)
- **GitHub Actions:** [.github/workflows/deploy-hot.yml](.github/workflows/deploy-hot.yml)
- **Standard deploy docs:** [CI_CD_SETUP.md](CI_CD_SETUP.md)

---

## 🎯 Summary

**Hot deployment** gives you:
- ✅ Zero downtime
- ✅ No workflow interruptions
- ✅ Faster deployments
- ✅ Same safety guarantees
- ✅ Instant rollback

**Use it for:** 99% of your deployments (all Python changes)

**Total setup time:** 0 minutes (already configured!)

🔥 **Ready to hot deploy!**
