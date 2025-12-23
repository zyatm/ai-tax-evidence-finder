#!/bin/bash
# Fix GitHub Actions Runner on Amazon Linux 2023
# The runner needs ICU libraries for .NET Core

set -e

echo "=========================================="
echo "Fixing GitHub Actions Runner for AL2023"
echo "=========================================="
echo ""

# Install ICU libraries for .NET Core
echo "==> Installing ICU libraries..."
sudo dnf install -y libicu

# Also install other .NET dependencies
echo "==> Installing additional .NET dependencies..."
sudo dnf install -y \
    ca-certificates \
    krb5-libs \
    libstdc++ \
    zlib \
    openssl-libs

echo ""
echo "✅ Dependencies installed!"
echo ""
echo "Now try running the runner configuration again:"
echo ""
echo "cd ~/actions-runner"
echo "./config.sh --url https://github.com/zyatm/ai-tax-evidence-finder --token YOUR_NEW_TOKEN"
echo ""
echo "Note: You'll need to get a NEW token from GitHub since the old one was likely consumed."
echo "Get it here: https://github.com/zyatm/ai-tax-evidence-finder/settings/actions/runners/new"
echo ""
