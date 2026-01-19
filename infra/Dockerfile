FROM python:3.11-slim

# -------------------------
# System setup
# -------------------------
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    cron \
    curl \
    && rm -rf /var/lib/apt/lists/*

# -------------------------
# Python dependencies
# -------------------------
# Support pip OR poetry (whichever you use)
COPY requirements.txt* pyproject.toml* poetry.lock* /app/

RUN if [ -f requirements.txt ]; then \
        pip install --no-cache-dir -r requirements.txt ; \
    fi

RUN if [ -f pyproject.toml ]; then \
        pip install --no-cache-dir poetry && \
        poetry config virtualenvs.create false && \
        poetry install --no-root ; \
    fi

# -------------------------
# App code
# -------------------------
COPY . /app

# Needed so "apps.worker", "apps.ui", etc. import correctly
ENV PYTHONPATH=/app

EXPOSE 8000
EXPOSE 9000
