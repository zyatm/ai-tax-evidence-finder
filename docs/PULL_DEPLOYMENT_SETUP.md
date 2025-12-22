# Pull-Based Deployment Setup

Three methods to deploy without SSH from GitHub Actions to EC2.

---

## 🎯 Option 1: GitHub Actions Self-Hosted Runner (Recommended)

EC2 instance runs a GitHub Actions runner that executes workflows locally.

### Architecture
```
┌─────────────┐         ┌──────────────────┐         ┌─────────────┐
│   GitHub    │  Job    │  EC2 Instance    │  Pull   │   GitHub    │
│   Actions   ├────────>│  (Runner Agent)  ├────────>│   Repo      │
└─────────────┘         └──────────────────┘         └─────────────┘
                               │
                               │ Deploy locally
                               ▼
                        ┌──────────────────┐
                        │  n8n + Python    │
                        │  (No SSH needed) │
                        └──────────────────┘
```

### Benefits
- ✅ No SSH keys in GitHub secrets
- ✅ EC2 pulls from GitHub (not pushed to)
- ✅ Uses existing GitHub Actions workflows
- ✅ Free for private repos
- ✅ Runs inside your VPC (secure)

---

### Setup Instructions

#### 1. Install Runner on EC2 (10 min)

SSH to your EC2 instance:
```bash
ssh -i ~/.ssh/your-key.pem ec2-user@YOUR_EC2_IP
```

Create runner directory:
```bash
mkdir -p ~/actions-runner && cd ~/actions-runner
```

Download and extract runner:
```bash
# Check latest version at: https://github.com/actions/runner/releases
RUNNER_VERSION="2.321.0"
curl -o actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz \
  -L https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz

tar xzf ./actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz
```

#### 2. Get Runner Token from GitHub

Go to your GitHub repo:
```
https://github.com/YOUR_USERNAME/ai-tax-evidence-finder/settings/actions/runners/new
```

Copy the token shown (starts with `A...`)

#### 3. Configure Runner

Back on EC2:
```bash
./config.sh \
  --url https://github.com/YOUR_USERNAME/ai-tax-evidence-finder \
  --token YOUR_RUNNER_TOKEN \
  --name ec2-production-runner \
  --labels production,ec2 \
  --work _work
```

When prompted:
- **Runner group**: Press Enter (default)
- **Runner name**: `ec2-production-runner`
- **Work folder**: Press Enter (default: `_work`)

#### 4. Install as a Service (Runs at Startup)

```bash
sudo ./svc.sh install
sudo ./svc.sh start
sudo ./svc.sh status
```

Verify it's running:
```bash
sudo systemctl status actions.runner.*
```

#### 5. Update GitHub Actions Workflow

Update `.github/workflows/deploy-hot.yml`:

```yaml
name: Hot Deploy (Pull-Based)

on:
  push:
    branches: [main]
    paths:
      - 'src/**'
      - 'config/**'
      - 'run.py'
      - 'requirements.txt'
  workflow_dispatch:

jobs:
  hot-deploy:
    name: Hot Deploy to EC2
    runs-on: [self-hosted, production]  # Uses your EC2 runner

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Create backup
        run: |
          TIMESTAMP=$(date +%Y%m%d-%H%M%S)
          sudo mkdir -p /app/backups

          if [ -d "/app/src" ]; then
            sudo tar -czf "/app/backups/hot-backup-$TIMESTAMP.tar.gz" \
              -C /app src config run.py 2>/dev/null || true
          fi

      - name: Hot deploy (atomic swap)
        run: |
          # Create staging area
          sudo mkdir -p /app/.staging
          sudo cp -r src /app/.staging/
          sudo cp -r config /app/.staging/
          sudo cp run.py /app/.staging/
          sudo cp requirements.txt /app/.staging/

          # Atomic swaps
          sudo mv /app/src /app/src.old 2>/dev/null || true
          sudo mv /app/.staging/src /app/src

          sudo mv /app/config /app/config.old 2>/dev/null || true
          sudo mv /app/.staging/config /app/config

          sudo mv /app/run.py /app/run.py.old 2>/dev/null || true
          sudo mv /app/.staging/run.py /app/run.py

          sudo mv /app/requirements.txt /app/requirements.txt.old 2>/dev/null || true
          sudo mv /app/.staging/requirements.txt /app/requirements.txt

          # Clean up
          sudo rm -rf /app/src.old /app/config.old /app/run.py.old /app/requirements.txt.old /app/.staging

      - name: Update dependencies
        run: |
          cd /app
          sudo pip3 install -r requirements.txt --quiet --upgrade 2>&1 | grep -v "already satisfied" || true

      - name: Set permissions
        run: |
          sudo chown -R 1000:1000 /app/src /app/config /app/run.py

      - name: Verify deployment
        run: |
          cd /app
          python3 -c "
          import sys
          sys.path.insert(0, 'src')
          from stage2_verbatim import VerbatimExtractor
          import os
          os.environ['ANTHROPIC_API_KEY'] = 'test-key'
          e = VerbatimExtractor(config_path='config/default_config.json')
          assert len(e.blocks) == 6
          print('✓ Extraction engine verified')
          "

      - name: Check n8n status
        run: |
          if docker ps | grep -q n8n; then
            echo "✓ n8n is still running (no restart)"
            docker ps --filter "name=n8n" --format "Status: {{.Status}}"
          else
            echo "⚠️ n8n container not found"
            exit 1
          fi

      - name: Deployment summary
        if: always()
        run: |
          echo "✅ Hot deployment complete"
          echo "   • Method: Pull-based (self-hosted runner)"
          echo "   • n8n: No restart"
          echo "   • Commit: ${{ github.sha }}"
```

#### 6. Test It

Push a change:
```bash
# Make a small change
echo "# Test change" >> src/README.md
git add src/README.md
git commit -m "test: Verify pull-based deployment"
git push
```

Watch it deploy:
```
https://github.com/YOUR_USERNAME/ai-tax-evidence-finder/actions
```

You should see the workflow run on your EC2 instance!

---

## 🎯 Option 2: AWS CodeDeploy

AWS-native continuous deployment service.

### Architecture
```
GitHub → AWS CodeDeploy → EC2 Agent pulls and deploys
```

### Setup

#### 1. Install CodeDeploy Agent on EC2

```bash
ssh -i ~/.ssh/your-key.pem ec2-user@YOUR_EC2_IP

# Install CodeDeploy agent
sudo yum install -y ruby wget
cd /home/ec2-user
wget https://aws-codedeploy-us-east-1.s3.us-east-1.amazonaws.com/latest/install
chmod +x ./install
sudo ./install auto

# Start and enable
sudo service codedeploy-agent start
sudo service codedeploy-agent status
```

#### 2. Create IAM Role for EC2

In AWS Console → IAM → Roles:
- Create role for EC2
- Attach policy: `AWSCodeDeployRole`
- Attach to your EC2 instance

#### 3. Create CodeDeploy Application

```bash
aws deploy create-application \
  --application-name ai-tax-evidence-finder \
  --compute-platform Server
```

#### 4. Create Deployment Group

```bash
aws deploy create-deployment-group \
  --application-name ai-tax-evidence-finder \
  --deployment-group-name production \
  --ec2-tag-filters Key=Name,Value=ai-tax-evidence-finder,Type=KEY_AND_VALUE \
  --service-role-arn arn:aws:iam::YOUR_ACCOUNT:role/CodeDeployServiceRole
```

#### 5. Create `appspec.yml`

Create in project root:
```yaml
version: 0.0
os: linux
files:
  - source: src/
    destination: /app/src
  - source: config/
    destination: /app/config
  - source: run.py
    destination: /app/run.py
  - source: requirements.txt
    destination: /app/requirements.txt

permissions:
  - object: /app
    owner: ec2-user
    group: ec2-user
    mode: 755

hooks:
  BeforeInstall:
    - location: scripts/codedeploy/before_install.sh
      timeout: 300
      runas: root

  AfterInstall:
    - location: scripts/codedeploy/after_install.sh
      timeout: 300
      runas: root

  ApplicationStart:
    - location: scripts/codedeploy/verify.sh
      timeout: 300
      runas: ec2-user
```

#### 6. Create Deployment Scripts

**scripts/codedeploy/before_install.sh**:
```bash
#!/bin/bash
set -e

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="/app/backups"

mkdir -p "$BACKUP_DIR"

if [ -d "/app/src" ]; then
    tar -czf "$BACKUP_DIR/backup-$TIMESTAMP.tar.gz" \
      -C /app src config run.py 2>/dev/null || true
fi
```

**scripts/codedeploy/after_install.sh**:
```bash
#!/bin/bash
set -e

cd /app
pip3 install -r requirements.txt --quiet --upgrade

chown -R 1000:1000 /app/src /app/config /app/run.py
```

**scripts/codedeploy/verify.sh**:
```bash
#!/bin/bash
set -e

cd /app
python3 -c "
import sys
sys.path.insert(0, 'src')
from stage2_verbatim import VerbatimExtractor
import os
os.environ['ANTHROPIC_API_KEY'] = 'test-key'
e = VerbatimExtractor(config_path='config/default_config.json')
assert len(e.blocks) == 6
print('✓ Deployment verified')
"
```

#### 7. Update GitHub Actions

```yaml
name: Deploy via CodeDeploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Create deployment package
        run: |
          mkdir -p package
          cp -r src config run.py requirements.txt appspec.yml scripts package/
          cd package
          zip -r ../deployment.zip .

      - name: Upload to S3
        run: |
          aws s3 cp deployment.zip \
            s3://your-deployment-bucket/ai-tax-evidence-finder/deployment-${{ github.sha }}.zip

      - name: Create CodeDeploy deployment
        run: |
          aws deploy create-deployment \
            --application-name ai-tax-evidence-finder \
            --deployment-group-name production \
            --s3-location bucket=your-deployment-bucket,key=ai-tax-evidence-finder/deployment-${{ github.sha }}.zip,bundleType=zip
```

---

## 🎯 Option 3: Polling Script on EC2

Simple cron job that checks GitHub for updates.

### Setup

#### 1. Create Polling Script

SSH to EC2 and create `/app/scripts/poll-and-deploy.sh`:

```bash
#!/bin/bash
set -e

REPO="https://github.com/YOUR_USERNAME/ai-tax-evidence-finder.git"
BRANCH="main"
WORK_DIR="/app/repo"
DEPLOY_DIR="/app"

# Initialize repo if needed
if [ ! -d "$WORK_DIR" ]; then
    git clone "$REPO" "$WORK_DIR"
    cd "$WORK_DIR"
    git checkout "$BRANCH"
fi

cd "$WORK_DIR"

# Fetch latest
git fetch origin "$BRANCH"

# Check if there are new commits
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/$BRANCH)

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "$(date): New changes detected, deploying..."

    # Pull changes
    git pull origin "$BRANCH"

    # Backup
    TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    sudo tar -czf "/app/backups/backup-$TIMESTAMP.tar.gz" \
      -C "$DEPLOY_DIR" src config run.py 2>/dev/null || true

    # Atomic deploy
    sudo mkdir -p /app/.staging
    sudo cp -r src /app/.staging/
    sudo cp -r config /app/.staging/
    sudo cp run.py /app/.staging/
    sudo cp requirements.txt /app/.staging/

    sudo mv /app/src /app/src.old 2>/dev/null || true
    sudo mv /app/.staging/src /app/src

    sudo mv /app/config /app/config.old 2>/dev/null || true
    sudo mv /app/.staging/config /app/config

    sudo mv /app/run.py /app/run.py.old 2>/dev/null || true
    sudo mv /app/.staging/run.py /app/run.py

    sudo mv /app/requirements.txt /app/requirements.txt.old 2>/dev/null || true
    sudo mv /app/.staging/requirements.txt /app/requirements.txt

    sudo rm -rf /app/src.old /app/config.old /app/run.py.old /app/requirements.txt.old /app/.staging

    # Update deps
    cd /app
    sudo pip3 install -r requirements.txt --quiet --upgrade

    # Verify
    python3 -c "
    import sys
    sys.path.insert(0, 'src')
    from stage2_verbatim import VerbatimExtractor
    import os
    os.environ['ANTHROPIC_API_KEY'] = 'test-key'
    e = VerbatimExtractor(config_path='config/default_config.json')
    print('✓ Deployed successfully')
    "

    echo "$(date): Deployment complete"
else
    echo "$(date): No changes detected"
fi
```

Make executable:
```bash
chmod +x /app/scripts/poll-and-deploy.sh
```

#### 2. Setup GitHub Personal Access Token

Create token at: https://github.com/settings/tokens

Give it `repo` scope, then:
```bash
# On EC2
git config --global credential.helper store
echo "https://YOUR_USERNAME:YOUR_TOKEN@github.com" > ~/.git-credentials
```

#### 3. Add to Cron

```bash
crontab -e
```

Add (checks every 5 minutes):
```
*/5 * * * * /app/scripts/poll-and-deploy.sh >> /var/log/auto-deploy.log 2>&1
```

Or use systemd timer for better control.

---

## 📊 Comparison

| Feature | Self-Hosted Runner | CodeDeploy | Polling Script |
|---------|-------------------|------------|----------------|
| **Setup complexity** | Medium | High | Low |
| **AWS dependency** | No | Yes | No |
| **Cost** | Free | Pay per deployment | Free |
| **Security** | High | High | Medium |
| **GitHub integration** | Native | Via webhook | None |
| **Deployment speed** | Instant | 1-2 min | Up to 5 min delay |
| **Rollback** | Manual | Built-in | Manual |

---

## ✅ Recommendation

**For your use case: Self-Hosted Runner (Option 1)**

Why:
- ✅ No SSH keys in GitHub
- ✅ Works with existing workflows
- ✅ Free
- ✅ Simple setup
- ✅ Instant deployments
- ✅ EC2 pulls, GitHub doesn't push

---

## 🚀 Quick Start (Self-Hosted Runner)

```bash
# 1. SSH to EC2
ssh -i ~/.ssh/your-key.pem ec2-user@YOUR_EC2_IP

# 2. Install runner
mkdir -p ~/actions-runner && cd ~/actions-runner
curl -o actions-runner-linux-x64-2.321.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.321.0/actions-runner-linux-x64-2.321.0.tar.gz
tar xzf ./actions-runner-linux-x64-2.321.0.tar.gz

# 3. Get token from GitHub (go to repo settings → Actions → Runners → New)
# Then configure:
./config.sh --url https://github.com/YOUR_USERNAME/ai-tax-evidence-finder --token YOUR_TOKEN

# 4. Install as service
sudo ./svc.sh install
sudo ./svc.sh start

# 5. Done! Update your GitHub workflow to use 'runs-on: [self-hosted, production]'
```

That's it! No more SSH keys, EC2 pulls from GitHub instead.
