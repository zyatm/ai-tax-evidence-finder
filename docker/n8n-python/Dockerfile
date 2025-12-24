FROM n8nio/n8n:latest

USER root

# Install Python and dependencies
RUN apk add --no-cache python3 py3-pip && \
    pip3 install --break-system-packages pdfplumber openpyxl pandas anthropic

USER node
