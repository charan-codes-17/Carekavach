FROM python:3.12-slim

# Prevent python from writing pyc files and buffer outputs
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# Install dependencies first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY app/ app/

# Non-root user for security hardening
RUN useradd -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# $PORT is injected at runtime by Render / Cloud Run
EXPOSE 8080

# --proxy-headers: trust X-Forwarded-For / X-Forwarded-Proto from Render's proxy
# --forwarded-allow-ips="*": accept forwarded headers from any upstream (Render LB)
# --workers 1: single process suits Render free-tier (512 MB RAM)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*' --workers 1"]
