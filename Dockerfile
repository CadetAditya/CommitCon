FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code, data, models, and static frontend
COPY . .

# Environment configuration
ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    AI_INFERENCE_URL=https://win-s6b0cl04s86.tailf0b46c.ts.net/chat \
    AI_INFERENCE_KEY=commitcon-secret-2026

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Launch uvicorn supporting dynamic cloud $PORT
CMD ["sh", "-c", "uvicorn phase5_api:app --host 0.0.0.0 --port ${PORT:-8000}"]

