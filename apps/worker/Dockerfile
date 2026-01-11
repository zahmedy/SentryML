FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY apps/worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY packages/core /app/packages/core
RUN pip install -e /app/packages/core

COPY apps/worker/worker ./worker

ENV PYTHONPATH=/app

CMD ["python", "-m", "worker.run_once"]