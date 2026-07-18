FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgeos-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Job outputs / uploads (ephemeral on Railway)
RUN mkdir -p /app/web_jobs /tmp/autotracker_jobs
ENV AUTOTRACKER_JOBS_DIR=/tmp/autotracker_jobs

EXPOSE 8000

CMD uvicorn webapp.main:app --host 0.0.0.0 --port ${PORT}
