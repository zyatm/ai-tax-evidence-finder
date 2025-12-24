#!/bin/bash
set -e

# Log all output
exec > >(tee /var/log/n8n-setup.log) 2>&1

echo "=========================================="
echo "n8n + 10-K Extraction Engine Setup"
echo "Started at: $(date)"
echo "=========================================="

# Variables from Terraform
DOMAIN_NAME="${domain_name}"
N8N_VERSION="${n8n_version}"
TIMEZONE="${timezone}"
PROJECT_NAME="${project_name}"

echo "Configuration:"
echo "  Domain: $DOMAIN_NAME"
echo "  n8n Version: $N8N_VERSION"
echo "  Timezone: $TIMEZONE"

# Update system
echo ">>> Updating system packages..."
dnf update -y

# Install Docker
echo ">>> Installing Docker..."
dnf install -y docker
systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user

# Install Docker Compose plugin
echo ">>> Installing Docker Compose..."
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Create directories
echo ">>> Creating directories..."
mkdir -p /opt/n8n
mkdir -p /opt/n8n/data
mkdir -p /opt/n8n/caddy/data
mkdir -p /opt/n8n/caddy/config

# Create extraction engine directories
mkdir -p /app/10k-inbox
mkdir -p /app/10k-processed
mkdir -p /app/output

# Set ownership
chown -R 1000:1000 /opt/n8n/data
chown -R 1000:1000 /app

# Install Python and extraction dependencies
echo ">>> Installing Python extraction dependencies..."
dnf install -y python3 python3-pip
pip3 install pdfplumber openpyxl pandas

# Download extraction engine
echo ">>> Setting up extraction engine..."
cat > /app/10k_extraction_engine.py << 'PYTHONSCRIPT'
"""
10-K EVIDENCE EXTRACTION ENGINE
Extracts financial evidence from SEC 10-K filings.
"""

import pdfplumber
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from pathlib import Path
import re
import sys
from datetime import datetime

EXTRACTION_CATEGORIES = {
    "depreciation / amortization": {"keywords": ["depreciation", "amortization", "useful life", "straight-line"], "block": "Fixed Assets"},
    "intangibles": {"keywords": ["intangible assets", "goodwill", "patents", "trademarks"], "block": "Fixed Assets"},
    "property, plant and equipment": {"keywords": ["property, plant and equipment", "PP&E", "fixed assets"], "block": "Fixed Assets"},
    "repair and maintenance": {"keywords": ["repair", "maintenance", "turnaround"], "block": "Fixed Assets"},
    "spare parts": {"keywords": ["spare parts", "critical spares", "catalysts"], "block": "Fixed Assets"},
    "building / leasehold improvement": {"keywords": ["building", "leasehold improvement"], "block": "Fixed Assets"},
    "m&a / asset acquisition": {"keywords": ["acquisition", "merger", "business combination"], "block": "Fixed Assets"},
    "expansion & construction": {"keywords": ["expansion", "construction", "capital project"], "block": "Fixed Assets"},
    "inventory": {"keywords": ["inventory", "LIFO", "FIFO", "raw materials"], "block": "Inventory"},
    "research and development": {"keywords": ["research and development", "R&D"], "block": "R&D"},
    "section 163j": {"keywords": ["163(j)", "interest limitation"], "block": "Tax"},
    "dtl / dta": {"keywords": ["deferred tax", "DTL", "DTA"], "block": "Tax"},
    "prepaid expense": {"keywords": ["prepaid", "advance payment"], "block": "Tax"},
    "deferred revenue": {"keywords": ["deferred revenue", "unearned revenue"], "block": "Tax"},
    "revenue recognition": {"keywords": ["revenue recognition", "ASC 606"], "block": "Tax"},
    "income statement": {"keywords": ["statement of income", "net income"], "block": "Statements"},
    "balance sheet": {"keywords": ["balance sheet", "total assets"], "block": "Statements"},
    "cash flow": {"keywords": ["statement of cash flows"], "block": "Statements"}
}

OUTPUT_COLUMNS = ["Potential Method Change List", "found in 10K", "SUMMARIZE", "found in trial balance", "found in tax return", "Potential Benefit or Exposure", "Low", "Mid", "High", "Timing", "Permanent"]

class PDFExtractor:
    def __init__(self, path):
        self.path = Path(path)
        self.pages = []
    def extract(self):
        with pdfplumber.open(self.path) as pdf:
            for i, page in enumerate(pdf.pages):
                self.pages.append({"num": i+1, "text": page.extract_text() or ""})
        return self.pages

class EvidenceFinder:
    def __init__(self, pages):
        self.pages = pages
    def find(self, config):
        matches = []
        for page in self.pages:
            for kw in config["keywords"]:
                if kw.lower() in page["text"].lower():
                    idx = page["text"].lower().find(kw.lower())
                    start, end = max(0, idx-800), min(len(page["text"]), idx+800)
                    matches.append(f"[Page {page['num']}]\n{page['text'][start:end].strip()}")
        return "\n\n---\n\n".join(matches[:5])

def process_10k(input_pdf, output_xlsx=None):
    path = Path(input_pdf)
    output_xlsx = output_xlsx or str(path.with_suffix('.xlsx'))
    print(f"Processing: {input_pdf}")
    
    pages = PDFExtractor(input_pdf).extract()
    finder = EvidenceFinder(pages)
    
    wb = Workbook()
    ws = wb.active
    ws.title = path.stem[:31]
    
    for col, h in enumerate(OUTPUT_COLUMNS, 1):
        ws.cell(row=1, column=col, value=h)
    
    row = 2
    for cat, cfg in EXTRACTION_CATEGORIES.items():
        ws.cell(row=row, column=1, value=cat)
        ws.cell(row=row, column=2, value=finder.find(cfg))
        row += 1
    
    wb.save(output_xlsx)
    print(f"Output: {output_xlsx}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python 10k_extraction_engine.py <input.pdf> [output.xlsx]")
        sys.exit(1)
    process_10k(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
PYTHONSCRIPT

chmod +x /app/10k_extraction_engine.py

# Create Caddyfile
cat > /opt/n8n/Caddyfile <<EOF
$DOMAIN_NAME {
    reverse_proxy n8n:5678
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        -Server
    }
}
EOF

# Create docker-compose.yml
cat > /opt/n8n/Dockerfile <<'DOCKERFILE'
FROM n8nio/n8n:latest

USER root

# Install Python and dependencies
RUN apk add --no-cache python3 py3-pip && \
    pip3 install --break-system-packages pdfplumber openpyxl pandas anthropic

USER node
DOCKERFILE

cat > /opt/n8n/docker-compose.yml <<EOF
version: '3.8'

services:
  n8n:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: n8n
    restart: unless-stopped
    environment:
      - N8N_HOST=$DOMAIN_NAME
      - N8N_PORT=5678
      - N8N_PROTOCOL=https
      - NODE_ENV=production
      - WEBHOOK_URL=https://$DOMAIN_NAME/
      - GENERIC_TIMEZONE=$TIMEZONE
      - TZ=$TIMEZONE
      - N8N_SECURE_COOKIE=true
      - ANTHROPIC_API_KEY=\${ANTHROPIC_API_KEY}
    volumes:
      - /opt/n8n/data:/home/node/.n8n
      - /app:/app
    networks:
      - n8n-network

  caddy:
    image: caddy:latest
    container_name: caddy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /opt/n8n/Caddyfile:/etc/caddy/Caddyfile:ro
      - /opt/n8n/caddy/data:/data
      - /opt/n8n/caddy/config:/config
    networks:
      - n8n-network
    depends_on:
      - n8n

networks:
  n8n-network:
    driver: bridge
EOF

# Create systemd service
cat > /etc/systemd/system/n8n.service <<EOF
[Unit]
Description=n8n Workflow Automation
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/n8n
ExecStart=/usr/local/lib/docker/cli-plugins/docker-compose up -d
ExecStop=/usr/local/lib/docker/cli-plugins/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable n8n.service

# Start containers
cd /opt/n8n
docker compose up -d

# Create helper scripts
cat > /usr/local/bin/n8n-logs <<'EOF'
#!/bin/bash
docker logs -f n8n
EOF
chmod +x /usr/local/bin/n8n-logs

cat > /usr/local/bin/n8n-restart <<'EOF'
#!/bin/bash
cd /opt/n8n && docker compose restart
EOF
chmod +x /usr/local/bin/n8n-restart

cat > /usr/local/bin/n8n-update <<'EOF'
#!/bin/bash
cd /opt/n8n && docker compose pull && docker compose up -d && docker image prune -f
EOF
chmod +x /usr/local/bin/n8n-update

cat > /usr/local/bin/n8n-backup <<'EOF'
#!/bin/bash
BACKUP_DIR="/opt/n8n/backups"
mkdir -p $BACKUP_DIR
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
tar -czf "$BACKUP_DIR/n8n-backup-$TIMESTAMP.tar.gz" -C /opt/n8n/data .
ls -t $BACKUP_DIR/n8n-backup-*.tar.gz | tail -n +8 | xargs -r rm
echo "Backup: $BACKUP_DIR/n8n-backup-$TIMESTAMP.tar.gz"
EOF
chmod +x /usr/local/bin/n8n-backup

cat > /usr/local/bin/extract-10k <<'EOF'
#!/bin/bash
python3 /app/10k_extraction_engine.py "$@"
EOF
chmod +x /usr/local/bin/extract-10k

echo "0 3 * * * root /usr/local/bin/n8n-backup" > /etc/cron.d/n8n-backup

echo "=========================================="
echo "Setup Complete! Access n8n at: https://$DOMAIN_NAME"
echo "=========================================="
