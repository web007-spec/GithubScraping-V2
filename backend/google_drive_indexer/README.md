# Public Google Drive Indexer

Indexes **only publicly accessible** Google Drive folders and files. The crawler never attempts to bypass authentication, CAPTCHAs, or permission walls.

## Features

- Recursive public folder discovery
- Category-based filtering (research papers, manuals, templates, PDFs, images, etc.)
- Async downloads with checksums and duplicate detection
- Text extraction (PDF, DOCX, XLSX, CSV, HTML, TXT)
- MongoDB storage with full-text search indexes
- REST API + Next.js UI with category picker before crawl

## Quick start

```bash
cd backend/google_drive_indexer
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env
```

Apply MongoDB indexes (from repo root):

```bash
python scripts/apply_mongodb_schema.py
```

Start the main API (`start-project.ps1`) and open:

- **Files:** http://localhost:3001/explore/drive
- **New crawl:** http://localhost:3001/explore/drive/crawl/new

## Crawl workflow

1. Paste one or more **public** Drive folder or file URLs
2. Select content categories (required)
3. Start crawl — worker runs as subprocess (`run_crawl_job.py`)
4. Only matching, publicly accessible files are downloaded and indexed

## Worker (manual)

```bash
set PYTHONPATH=..\..
python run_crawl_job.py <crawl_run_id>
```

## Docker

```bash
docker compose up --build
```

Requires `MONGODB_URI` pointing to a reachable MongoDB instance.

## Legal / ethical use

Use only for content you are permitted to access and index. This tool is designed for public sharing links only.
