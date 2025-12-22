FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY run.py .
COPY config/ ./config/

# Create directories for input/output
RUN mkdir -p /data/input /data/output /data/processed

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import sys; sys.path.insert(0, 'src'); from stage2_verbatim import VerbatimExtractor; print('healthy')" || exit 1

# Default entrypoint
ENTRYPOINT ["python", "run.py"]
CMD ["--help"]
