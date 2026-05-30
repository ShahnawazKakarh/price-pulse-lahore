# Price Pulse Lahore

> Live daily market rates for Lahore — vegetables, fruits, poultry & essential commodities.
> AI-powered OCR from Punjab Government official data. Built by [QA Pulse by SK](https://skakarh.com)

[![Live UI](https://img.shields.io/badge/Live-GitHub%20Pages-blue)](https://shahnawazkakarh.github.io/price-pulse-lahore)
[![API Docs](https://img.shields.io/badge/API-FastAPI-green)](https://price-pulse-lahore.vercel.app/docs)
[![Data Source](https://img.shields.io/badge/Data-Punjab%20Govt-orange)](https://lahore.punjab.gov.pk/market_rates)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![Model](https://img.shields.io/badge/AI-Gemini%202.5%20Flash-purple)](https://aistudio.google.com)

---

## What is this?

**Price Pulse Lahore** automatically scrapes the official Punjab Government daily market rate JPEGs, extracts structured price data using **Google Gemini 2.5 Flash Vision AI**, stores it in a time-series database, and serves it via a REST API with a live ticker UI.

People of Lahore can check today's prices, see what went up or down, search items, and filter by category — without navigating government websites.

---

## Live Links

| Resource | URL |
|---|---|
| Live UI | https://shahnawazkakarh.github.io/price-pulse-lahore |
| API | https://price-pulse-lahore.vercel.app |
| API Docs | https://price-pulse-lahore.vercel.app/docs |
| Data Source | https://lahore.punjab.gov.pk/market_rates |

---

## Features

- [x] Automated daily scraper — runs at 7:30am PKT via Railway cron
- [x] AI Vision OCR — Gemini 2.5 Flash extracts prices from government JPEGs
- [x] Failure alerts via Telegram
- [x] PostgreSQL + TimescaleDB time-series storage
- [x] REST API with FastAPI — 8 endpoints, rate limiting, CORS
- [x] Live ticker UI on GitHub Pages — search, filters, sort, movers
- [x] JSON fallback — works without database
- [ ] Price trend charts (Phase 2)
- [ ] Price alerts / notifications (Phase 2)
- [ ] AI price forecasting (Phase 3)

---

## Project Structure

```
price-pulse-lahore/
├── scraper/
│   ├── scraper.py         # Fetches images from gov site (1 per category)
│   ├── ocr.py             # Gemini 2.5 Flash extracts prices from images
│   └── pipeline.py        # Orchestrates: scrape → OCR → DB/JSON
├── api/
│   └── main.py            # FastAPI — 8 REST endpoints
├── db/
│   ├── models.py          # SQLAlchemy ORM: items, price_readings, scrape_logs
│   ├── database.py        # Connection, sessions, TimescaleDB setup
│   └── crud.py            # Fuzzy matching, price upsert, query helpers
├── alerts/
│   └── telegram.py        # Failure alerting via Telegram bot
├── alembic/               # DB migration versioning
├── docs/
│   └── index.html         # GitHub Pages live UI
├── data/
│   ├── images/            # Downloaded JPEGs (local cache)
│   └── daily/             # OCR output JSON (DB fallback)
├── .env.example           # Environment variable template
├── requirements.txt       # Python dependencies
├── setup.sh               # One-command setup script
├── railway.toml           # Railway deployment config
└── Procfile               # Process definitions
```

---

## Quick Start

### 1. Clone & setup

```bash
git clone https://github.com/ShahnawazKakarh/price-pulse-lahore.git
cd price-pulse-lahore
chmod +x setup.sh
./setup.sh
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in your keys
```

| Variable | Where to get it | Required |
|---|---|---|
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) → Get API Key | ✅ Yes |
| `DATABASE_URL` | Railway Postgres or local PostgreSQL | Production |
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/BotFather) on Telegram | Optional |
| `TELEGRAM_CHAT_ID` | [@userinfobot](https://t.me/userinfobot) on Telegram | Optional |
| `TEST_MODE` | `true` = vegetables only, `false` = all 4 categories | Optional |

> **Gemini model used:** `gemini-2.5-flash` — free tier, 20 RPD, 5 RPM
> Requires `google-genai >= 2.7.0` — install via `pip install --upgrade google-genai`

### 3. Activate virtual environment

```bash
# Required in every new terminal session
source venv/bin/activate
```

### 4. Run the pipeline

```bash
python scraper/pipeline.py
```

### 5. Start the API

```bash
uvicorn api.main:app --reload --port 8000
# Docs at: http://localhost:8000/docs
```

### 6. Open the UI

```bash
open docs/index.html
```

---

## API Endpoints

| Method | Endpoint | Description | Rate limit |
|---|---|---|---|
| GET | `/` | API info and endpoint list | — |
| GET | `/health` | Health check — DB status, latest data | — |
| GET | `/today` | All prices for today (`?category=` filter) | 60/min |
| GET | `/movers` | Top gainers and losers today | 60/min |
| GET | `/categories` | Summary stats per category | 60/min |
| GET | `/search?q=tomato` | Search by name (English or Urdu) | 30/min |
| GET | `/item/{slug}` | Single item current price | 60/min |
| GET | `/item/{slug}/history` | Price history — requires DB | 30/min |

---

## Useful Commands

```bash
# ── Setup ──────────────────────────────────────────────────────────────────
# One-time setup
chmod +x setup.sh && ./setup.sh

# Activate venv (every new terminal)
source venv/bin/activate

# Install / upgrade dependencies
pip install -r requirements.txt
pip install --upgrade google-genai   # must be >= 2.7.0

# ── Pipeline ───────────────────────────────────────────────────────────────
# Run full pipeline (scrape → OCR → save)
python scraper/pipeline.py

# Force re-download (clear processed markers)
find data/images/ -name "*.processed" -delete && python scraper/pipeline.py

# Test OCR on a single image
python scraper/ocr.py data/images/your_image.jpg vegetables

# ── API ────────────────────────────────────────────────────────────────────
# Start API (development, auto-reload)
uvicorn api.main:app --reload --port 8000

# Start API (production)
uvicorn api.main:app --host 0.0.0.0 --port 8000

# Open in browser (Mac)
open http://localhost:8000/docs                               # Interactive API docs
open http://localhost:8000/today                              # Today's prices
open http://localhost:8000/health                             # Health check

# Open live GitHub Pages UI
open https://shahnawazkakarh.github.io/price-pulse-lahore

# Open local UI (needs API running on port 8000)
open docs/index.html

# Quick API checks via curl
curl http://localhost:8000/health
curl http://localhost:8000/today | python3 -m json.tool
curl http://localhost:8000/movers | python3 -m json.tool
curl "http://localhost:8000/search?q=tomato"

# ── Database ───────────────────────────────────────────────────────────────
# Initialise DB manually
python db/database.py

# Run migrations
alembic upgrade head

# ── Data ───────────────────────────────────────────────────────────────────
# Check today's extracted data
cat data/daily/$(date +%Y-%m-%d).json | python3 -m json.tool

# List all daily JSON files
ls -la data/daily/

# List downloaded images
ls -la data/images/

# ── Alerts ─────────────────────────────────────────────────────────────────
# Test Telegram alerts
python alerts/telegram.py

# ── Git ────────────────────────────────────────────────────────────────────
git add -A
git commit -m "your message"
git push origin master
```

---

## Environment Modes

| Mode | Setting | Behaviour |
|---|---|---|
| Development | `TEST_MODE=true` | Scrapes vegetables only — 1 OCR call |
| Production | `TEST_MODE=false` | All 4 categories — 4 OCR calls/day |
| No DB | `DATABASE_URL` not set | Falls back to `data/daily/*.json` |

---

## Gemini API Notes

- **Model:** `gemini-2.5-flash` (requires SDK >= 2.7.0)
- **Free tier limits:** 20 requests/day, 5 requests/minute
- **We use:** 4 OCR calls/day (1 per category) — well within free limits
- **Quota resets:** midnight Pacific Time (1pm PKT)
- **Key source:** [aistudio.google.com/app/api-keys](https://aistudio.google.com/app/api-keys)
- **Important:** Create key with **no application restrictions**

---

## Vercel Deployment (API)

```bash
# 1. Push to GitHub
git push origin master

# 2. Go to vercel.com → New Project → Import from GitHub
# Select: ShahnawazKakarh/price-pulse-lahore
# Framework: Other

# 3. Add environment variables in Vercel dashboard:
GEMINI_API_KEY=your_key
DATABASE_URL=your_supabase_pooler_url
TEST_MODE=false
ENV=production

# 4. Deploy — API live at price-pulse-lahore.vercel.app
```

## GitHub Actions Cron Job

```bash
# Runs automatically at 2:30 AM UTC (7:30 AM PKT) daily
# Add secrets in: github.com/ShahnawazKakarh/price-pulse-lahore/settings/secrets/actions
# Required: GEMINI_API_KEY, DATABASE_URL
# Optional: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# Manual trigger:
# GitHub → Actions → Daily Price Pipeline → Run workflow
```

---

## Data Source

Official daily market rates published by the **Government of Punjab, Lahore**.
Source: [lahore.punjab.gov.pk/market_rates](https://lahore.punjab.gov.pk/market_rates)

Data is extracted from WhatsApp-forwarded JPEG images using Google Gemini 2.5 Flash Vision AI.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Scraper | Python 3.12, httpx, BeautifulSoup |
| AI OCR | Google Gemini 2.5 Flash Vision |
| Database | PostgreSQL + TimescaleDB |
| ORM | SQLAlchemy + Alembic |
| API | FastAPI, uvicorn, slowapi |
| Fuzzy matching | rapidfuzz |
| Alerts | Telegram Bot API |
| Frontend | Vanilla JS, GitHub Pages |
| Hosting | Railway |

---

**Built by [Shahnawaz Khan](https://skakarh.com) · QA Pulse by SK**
