# Google Docs Public Indexer

Production-ready Python application that discovers, downloads, parses, and indexes **publicly accessible Google Docs only**. The indexer respects access controls: it does not bypass authentication, CAPTCHAs, or permissions, and skips documents that require sign-in.

## Features

- **Discovery** — Import URLs from text files or search API result lists
- **Async crawler** — 50–100 concurrent workers with rate limiting and retries
- **Public export endpoints** — HTML, TXT, and optional PDF download
- **Rich parsing** — Title, headings, paragraphs, lists, tables, links, images
- **Duplicate detection** — SHA256 content hashing + unique doc ID / URL constraints
- **Supabase PostgreSQL** — Full persistence with crawl logs and statistics
- **Resume & retry** — Interrupted crawls and failed downloads can be resumed
- **Search & export** — Full-text, title, keyword, language, and date filters; CSV/JSON/Markdown export
- **CLI** — Typer-based commands for all operations
- **Docker** — Containerized deployment with PostgreSQL

## Architecture

```mermaid
flowchart TB
    subgraph Input
        URL[URL List File]
        Search[Search API Results]
    end

    subgraph Discovery
        DS[DiscoveryService]
        Norm[URL Normalizer]
    end

    subgraph Crawler
        Q[asyncio.Queue]
        W1[Worker Pool]
        DL[DocumentDownloader]
    end

    subgraph Processing
        P[DocumentParser]
        C[Text Cleaner]
        H[SHA256 Hasher]
    end

    subgraph Storage
        PG[(Supabase PostgreSQL)]
        SB[Supabase REST API]
    end

    URL --> DS
    Search --> DS
    DS --> Norm
    Norm --> PG
    PG --> Q
    Q --> W1
    W1 --> DL
    DL --> P
    P --> C
    C --> H
    H --> PG
    PG -. optional .-> SB
```

## Project Structure

```
google_docs_indexer/
├── app/
│   ├── config/          # Pydantic settings
│   ├── crawler/         # Discovery + queue/workers
│   ├── downloader/      # Async httpx downloader
│   ├── parser/          # BeautifulSoup + selectolax parser
│   ├── database/        # SQLAlchemy engine + repositories
│   ├── models/          # ORM models
│   ├── services/        # Business logic layer
│   ├── utils/           # URL, hashing, logging, rate limiter
│   └── cli/             # Typer CLI
├── tests/
├── migrations/          # Alembic + SQL schema
├── docker/
├── data/                # URL lists and exports
├── logs/                # Rotating log files
├── main.py
├── requirements.txt
├── docker-compose.yml
└── .env.example
```

## Requirements

- Python 3.12+
- PostgreSQL (Supabase or local)
- Public Google Docs URLs (documents shared as "Anyone with the link")

## Installation

### Local setup

```bash
cd google_docs_indexer
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Supabase credentials
```

### Docker

```bash
cp .env.example .env
# Set DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/postgres

docker compose up -d db
docker compose run --rm indexer discover
docker compose run --rm indexer crawl --workers 50
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `SUPABASE_URL` | Supabase project URL | — |
| `SUPABASE_KEY` | Supabase service/anon key | — |
| `DATABASE_URL` | Async SQLAlchemy connection string | local postgres |
| `MAX_WORKERS` | Concurrent crawl workers | `50` |
| `DOWNLOAD_TIMEOUT` | HTTP timeout (seconds) | `30` |
| `RATE_LIMIT` | Requests per second | `10` |
| `USER_AGENT` | HTTP User-Agent header | indexer default |
| `LOG_LEVEL` | DEBUG, INFO, WARNING, ERROR | `INFO` |
| `EXPORT_FORMATS` | Comma-separated: html, txt, pdf | `html,txt` |
| `URL_LIST_FILE` | Default URL input file | `data/urls.txt` |

## Supabase Setup

1. Create a project at [supabase.com](https://supabase.com).
2. Go to **Project Settings → Database** and copy the connection string.
3. Convert to async format:
   ```
   postgresql+asyncpg://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
   ```
4. Set `DATABASE_URL`, `SUPABASE_URL`, and `SUPABASE_KEY` in `.env`.
5. Apply schema:

   ```bash
   # Option A: Alembic
   alembic upgrade head

   # Option B: SQL file in Supabase SQL Editor
   # Paste contents of migrations/schema.sql
   ```

## Database Schema

| Table | Purpose |
|-------|---------|
| `documents` | Indexed docs with title, text, HTML, hashes, status |
| `links` | Hyperlinks extracted from documents |
| `images` | Image URLs extracted from documents |
| `crawl_logs` | Per-request status, errors, timing |
| `statistics` | Aggregated metrics for dashboard |

## Usage

### Search and scrape (recommended — no manual URLs)

**Single search** (finds ~25-50 docs):
```bash
python main.py crawl-csv --search "resume template" --max-results 50
```

**Batch search for thousands of docs** (uses `data/queries.txt`):
```bash
# Discover + crawl up to 10,000 unique public docs
python main.py crawl-csv --batch-search --target 10000 --workers 100

# Search only (URLs saved incrementally, safe to interrupt)
python main.py crawl-csv --batch-search --target 5000 --queries data/queries.txt

# Crawl already-discovered URLs (resume after interrupt)
python main.py crawl-csv --from-discovered --resume --workers 100
```

How scale works:
- Each query in `data/queries.txt` finds ~25-50 unique docs via the `ddgs` search engine
- 200+ queries × 50 results = **10,000+ unique documents**
- URLs append to `data/discovered_urls.txt` incrementally (resume-safe)
- Results append to `data/results.csv` with `--resume` (skips already crawled)

Optional API keys for higher volume (set in `.env`):
- `GOOGLE_CSE_API_KEY` + `GOOGLE_CSE_ID` — Google Custom Search (100 results/query)
- `BING_SEARCH_API_KEY` — Bing Web Search API (1000 results/query)

### Manual URL list

Add publicly shared Google Docs URLs to `data/urls.txt` (one per line), then:

```bash
# 1. Discover and register URLs
python main.py discover

# 2. Crawl and index
python main.py crawl --workers 50 --limit 10000

# 3. Resume interrupted crawl
python main.py resume

# 4. Retry failed downloads
python main.py retry --limit 500

# 5. View statistics
python main.py stats

# 6. Search indexed documents
python main.py search --query "machine learning" --limit 20
python main.py search --title "Report" --lang en --full-text

# 7. Export results
python main.py export --format json -o data/export.json
python main.py export --format csv -o data/export.csv
python main.py export --format markdown -o data/export.md

# 8. Clean text (utility)
python main.py clean "  messy   text  "
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `discover` | Load URLs from file, normalize, deduplicate, save to DB |
| `crawl` | Download and parse queued documents |
| `resume` | Continue processing pending documents |
| `retry` | Re-attempt failed downloads |
| `stats` | Show statistics dashboard |
| `search` | Search by query, title, language, date |
| `export` | Export to CSV, JSON, or Markdown |
| `clean` | Run text cleaner on input string |

## How Public Access Works

The indexer uses Google's public export URLs:

```
https://docs.google.com/document/d/{DOC_ID}/export?format=html
https://docs.google.com/document/d/{DOC_ID}/export?format=txt
```

Documents must be shared with **"Anyone with the link"** (viewer access). Private documents return HTTP 401/403 or a login page and are marked as `failed` — never bypassed.

## Performance

- **Concurrency**: Configure `MAX_WORKERS` up to 100
- **Connection pooling**: httpx with 100 max connections
- **Rate limiting**: Token-bucket limiter per worker pool
- **Memory**: Streaming-friendly design; HTML stored per document
- **Scale**: Batch queue loading (10k+ documents per run)

## Testing

```bash
pip install -r requirements.txt
pytest tests/ -v

# With coverage
pytest tests/ --cov=app --cov-report=term-missing
```

Integration tests require `DATABASE_URL` or `TEST_DATABASE` set.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Document is not publicly accessible` | Ensure doc is shared publicly |
| Connection refused to DB | Check `DATABASE_URL` and network |
| Rate limiting / timeouts | Lower `MAX_WORKERS` or `RATE_LIMIT` |
| Empty search results | Run `crawl` first; check `stats` |
| Alembic enum errors | Use `migrations/schema.sql` on fresh DB |

## Deployment

1. Set environment variables in your host or secrets manager.
2. Run migrations: `alembic upgrade head`
3. Use Docker Compose or run `python main.py crawl` on a schedule (cron/Kubernetes Job).
4. Mount persistent volumes for `data/` and `logs/`.
5. Monitor via `python main.py stats` or query the `statistics` table.

## License

Use responsibly. Only index documents you have permission to access. This tool is designed for publicly shared Google Docs and does not circumvent Google's access controls.
