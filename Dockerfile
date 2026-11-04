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

# Launch application via universal runner
CMD ["python", "run.py"]
