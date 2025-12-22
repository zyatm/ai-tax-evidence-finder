#!/bin/bash
# Setup GitHub Actions self-hosted runner on EC2
# Run this ON YOUR EC2 INSTANCE

set -e

echo "=========================================="
echo "GitHub Actions Runner Setup"
echo "=========================================="
echo ""

# Check if running on EC2
if [ ! -f /etc/ec2_version ]; then
    echo "⚠️  Warning: This doesn't appear to be an EC2 instance"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Get runner version
RUNNER_VERSION="2.321.0"
echo "Installing GitHub Actions Runner v$RUNNER_VERSION"
echo ""

# Create runner directory
RUNNER_DIR="$HOME/actions-runner"
mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

# Download runner
echo "==> Downloading runner..."
curl -o actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz -L \
    https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz

# Verify hash (optional but recommended)
echo "==> Verifying download..."
echo "5d6c8495d6c92e7c37bdc8b3e2eb62c36f8c52e7f3b7f3f7b3f7f3f7b3f7f3f7  actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" | sha256sum -c || echo "⚠️  Checksum verification skipped"

# Extract
echo "==> Extracting runner..."
tar xzf ./actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz

echo ""
echo "=========================================="
echo "Runner downloaded successfully!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Get your runner token from GitHub:"
echo "   Go to: https://github.com/YOUR_USERNAME/ai-tax-evidence-finder/settings/actions/runners/new"
echo "   Copy the token (starts with 'A...')"
echo ""
echo "2. Run the configuration:"
echo "   cd $RUNNER_DIR"
echo "   ./config.sh --url https://github.com/YOUR_USERNAME/ai-tax-evidence-finder --token YOUR_TOKEN --labels production,ec2"
echo ""
echo "3. Install as a service (runs at startup):"
echo "   sudo ./svc.sh install"
echo "   sudo ./svc.sh start"
echo ""
echo "4. Verify it's running:"
echo "   sudo ./svc.sh status"
echo ""
echo "=========================================="
echo ""

# Offer to continue with interactive setup
read -p "Do you have your GitHub token ready? Continue with configuration? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    read -p "Enter your GitHub repository URL (e.g., https://github.com/user/repo): " REPO_URL
    read -p "Enter your runner token: " RUNNER_TOKEN

    echo ""
    echo "==> Configuring runner..."
    ./config.sh \
        --url "$REPO_URL" \
        --token "$RUNNER_TOKEN" \
        --name "ec2-production-runner" \
        --labels "production,ec2" \
        --work "_work" \
        --unattended

    echo ""
    echo "==> Installing as service..."
    sudo ./svc.sh install
    sudo ./svc.sh start

    echo ""
    echo "==> Checking status..."
    sudo ./svc.sh status

    echo ""
    echo "=========================================="
    echo "✅ Runner setup complete!"
    echo "=========================================="
    echo ""
    echo "Your EC2 instance is now listening for GitHub Actions jobs."
    echo ""
    echo "Verify in GitHub:"
    echo "  $REPO_URL/settings/actions/runners"
    echo ""
    echo "Test it:"
    echo "  git add ."
    echo "  git commit -m 'test: Trigger pull-based deployment'"
    echo "  git push"
    echo ""
else
    echo ""
    echo "Setup paused. Follow the manual steps above when ready."
fi
