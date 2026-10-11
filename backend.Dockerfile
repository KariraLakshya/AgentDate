# Hosted backend image. Build context is the repo root so data/ (personas + demo bundle) ships with the API.
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY data/ ./data/
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
