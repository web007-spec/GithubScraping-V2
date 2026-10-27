FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app:/app/../..
ENV DOWNLOAD_PATH=/app/downloads
ENV THUMBNAIL_PATH=/app/thumbnails

CMD ["python", "run_crawl_job.py"]
