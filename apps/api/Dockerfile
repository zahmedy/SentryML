FROM python:3.11-slim

WORKDIR /app

# System deps (psycopg needs these)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY apps/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY apps/api/app ./app
COPY apps/api/scripts ./scripts

ENV PYTHONPATH=/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]