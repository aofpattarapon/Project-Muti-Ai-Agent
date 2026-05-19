# ============================================================
# Multi-AI-Agent SDLC System - Dockerfile
# Python 3.11 slim image
# ============================================================

FROM python:3.11-slim

# Metadata
LABEL maintainer="SDLC Multi-Agent System"
LABEL description="AI Agent for SDLC Automation"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 agent
WORKDIR /app

# Copy requirements first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=agent:agent . .

# Create necessary directories
RUN mkdir -p /app/data /app/outputs && \
    chown -R agent:agent /app/data /app/outputs

# Switch to non-root user
USER agent

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import discord; print('OK')" || exit 1

# Default command (override in docker-compose)
CMD ["python", "-m", "agents.ceo.agent"]
