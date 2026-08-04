# Stage 1: Build
FROM python:3.13-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
  build-essential \
  libpq-dev \
  && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
  libpq5 \
  curl \
  && rm -rf /var/lib/apt/lists/*

RUN addgroup --system app \
  && adduser --system --ingroup app --home /app app \
  && mkdir -p /app/data /app/logs /app/backups

COPY --from=builder /opt/venv /opt/venv
COPY . .
RUN chown -R app:app /app

ENV PATH=/opt/venv/bin:$PATH
ENV PYTHONUNBUFFERED=1
USER app

# Health check using the HealthServer
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

EXPOSE 8080
# Webhook port (used when BOT_MODE=webhook)
EXPOSE 8443

CMD ["python", "main.py"]
