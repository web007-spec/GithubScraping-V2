# Outreach Console — Management Platform

Next.js admin UI + FastAPI API. **MongoDB** is the primary store (auth, GitHub users, Drive, schedules). No Redis required.

```
Next.js (:3001) ──JWT──► FastAPI (:8000) ──► MongoDB (outreach_console)
                              │
                              ├── scrape subprocess ──► GitHub API
                              ├── Drive/Docs crawl workers
                              └── APScheduler ──► scheduled_jobs
```

## Prerequisites

- Python 3.11+, Node.js 18+
- MongoDB on `127.0.0.1:27017` (`.\start-mongo.ps1` for portable install under `.tools\mongodb`)

## 1. Environment

### Backend — `backend/github_Scraping/.env`

Copy from `backend/github_Scraping/.env.example`:

```env
MONGODB_URI=mongodb://127.0.0.1:27017
MONGODB_DB_NAME=outreach_console
DATABASE_STORAGE=mongodb
GOOGLE_DOCS_STORAGE=mongodb
AUTH_JWT_SECRET=generate_a_long_random_secret_string_at_least_32_chars
TOKEN_ENCRYPTION_KEY=generate_a_long_random_secret_string
API_HOST=0.0.0.0
API_PORT=8000
CORS_ALLOW_NETWORK=true
CORS_ORIGINS=http://localhost:3001
ADMIN_ROLE=admin
ALLOW_PUBLIC_REGISTRATION=true
```

Generate secrets:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Frontend — `frontend/.env` (or `.env.local`)

See `frontend/.env.local.example`:

```env
PORT=3001
NEXT_PUBLIC_DATABASE_STORAGE=mongodb
API_PROXY_TARGET=http://127.0.0.1:8000
NEXT_PUBLIC_SUPABASE_URL=https://example.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=placeholder
```

## 2. Database schema

```powershell
.\start-mongo.ps1
python scripts\apply_mongodb_schema.py
```

Do **not** run `schema/*.sql` when using MongoDB. See `schema/mongodb/README.md`.

## 3. Run

```powershell
.\start-project.ps1 -Install   # first time (deps)
.\start-project.ps1            # later
```

- UI: http://127.0.0.1:3001  
- API: http://127.0.0.1:8000/docs  
- Health: http://127.0.0.1:8000/health  

Stop:

```powershell
.\stop-project.ps1 -CloseShellWindows
```

### Manual windows

```powershell
cd backend\github_Scraping
.\start-api.ps1

cd frontend
.\start-frontend.ps1
```

## 4. First login

1. Open `/register` (requires `ALLOW_PUBLIC_REGISTRATION=true`).
2. Sign in at `/login`.
3. **Tokens** → add a GitHub PAT.
4. **New Scrape** → start a run; browse results under **Users**.

## 5. LAN access

```powershell
.\scripts\show-lan-urls.ps1
```

Allow firewall TCP **3001** and **8000**. Other PCs open `http://YOUR_LAN_IP:3001`.

## 6. Product modules

| Module | Notes |
|--------|--------|
| GitHub scraping | Dashboard, scrapes, users, tokens, schedules, logs |
| Google Drive | Public browse + admin crawl |
| Google Docs | Legacy routes still exist under `/explore/docs` but are **hidden** from nav |
| Team chat / Chrome extension / releases | Removed from UI **and** API |

## 7. Optional CLI scraper

```powershell
python scrape_github_users.py --target-countries US,India --max-per-location 100
```

Uses scraper code from `backend/github_Scraping/app/scraper/`. Prefer the UI for normal use.
