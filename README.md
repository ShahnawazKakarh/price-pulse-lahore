# Price Pulse Lahore

> Live daily market rates for Lahore — vegetables, fruits, poultry & essential commodities.
> AI-powered OCR from Punjab Government official data. Built by [QA Pulse by SK](https://skakarh.com)

[![Live UI](https://img.shields.io/badge/Live-GitHub%20Pages-blue)](https://shahnawazkakarh.github.io/price-pulse-lahore)
[![API](https://img.shields.io/badge/API-Vercel-black)](https://price-pulse-lahore.vercel.app)
[![API Docs](https://img.shields.io/badge/Docs-FastAPI-green)](https://price-pulse-lahore.vercel.app/docs)
[![Data Source](https://img.shields.io/badge/Data-Punjab%20Govt-orange)](https://lahore.punjab.gov.pk/market_rates)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![AI](https://img.shields.io/badge/AI-Gemini%202.5%20Flash-purple)](https://aistudio.google.com)

---

## What is this?

**Price Pulse Lahore** automatically scrapes the official Punjab Government daily market rate JPEGs, extracts structured price data using **Google Gemini 2.5 Flash Vision AI**, stores it in a PostgreSQL database, and serves it via a REST API with a live dashboard UI.

People of Lahore can check today's prices, see what went up or down, search items, filter by category, and calculate their weekly grocery basket — without navigating government websites.

---

## Live

| | URL |
|---|---|
| 🌐 **Live UI** | https://shahnawazkakarh.github.io/price-pulse-lahore |
| ⚡ **API** | https://price-pulse-lahore.vercel.app |
| 📖 **API Docs** | https://price-pulse-lahore.vercel.app/docs |
| 📊 **Data Source** | https://lahore.punjab.gov.pk/market_rates |

---

## Features

**Data**
- Automated daily scraper — government JPEG images downloaded every morning
- AI Vision OCR — Gemini 2.5 Flash extracts structured prices from images
- PostgreSQL + Supabase for time-series storage
- JSON fallback — works without database in development

**UI** — [shahnawazkakarh.github.io/price-pulse-lahore](https://shahnawazkakarh.github.io/price-pulse-lahore)
- Live scrolling price ticker
- Category summary cards with inflation signal
- Sortable, filterable price table with 7-day sparklines
- Click any item → detail modal with price chart
- 🛒 Basket calculator — select items, see total cost
- 🔥 Alert banner — biggest mover of the day
- اردو Urdu / English bilingual toggle (RTL support)
- Top gainers & losers section

**API** — [price-pulse-lahore.vercel.app/docs](https://price-pulse-lahore.vercel.app/docs)
- 12 REST endpoints with rate limiting and CORS
- Analytics: anomaly detection, inflation index, price forecasting

**Automation**
- GitHub Actions cron — runs daily, zero manual work
- Failure alerts via Telegram

### 🤖 ML Roadmap

| Phase | Timeline | Feature | Method |
|---|---|---|---|
| **Phase 1** | ✅ Live | Anomaly detection, inflation index, linear forecast | Rule-based + statistics |
| **Phase 2** | 30 days data | Z-score anomalies, day-of-week patterns, moving averages | Statistical models |
| **Phase 3** | 90 days data | Price forecasting with confidence bands, seasonal decomposition | Meta Prophet |
| **Phase 4** | 6 months data | LSTM predictions, Ramadan price tracker, correlation matrix | TensorFlow / PyTorch |

> Data collection started May 2026. ML models activate automatically as historical data grows.

---

## Project Structure

```
price-pulse-lahore/
├── scraper/
│   ├── scraper.py         # Fetches images from gov site
│   ├── ocr.py             # Gemini Vision extracts prices
│   └── pipeline.py        # Daily orchestrator: scrape → OCR → DB
├── api/
│   ├── main.py            # FastAPI — core price endpoints
│   └── analytics.py       # Analytics & ML endpoints
├── db/
│   ├── models.py          # SQLAlchemy ORM models
│   ├── database.py        # Connection & session management
│   └── crud.py            # Fuzzy matching, upserts, query helpers
├── alerts/
│   └── telegram.py        # Failure alerting
├── docs/
│   └── index.html         # GitHub Pages live UI
├── .github/
│   └── workflows/
│       └── daily_pipeline.yml  # GitHub Actions cron job
├── data/
│   ├── images/            # Downloaded JPEGs (local cache)
│   └── daily/             # JSON fallback output
├── seed_db.py             # One-time DB seeder from JSON files
├── .env.example           # Environment variable template
├── requirements.txt
└── setup.sh               # One-command local setup
```

---

## Quick Start

```bash
git clone https://github.com/ShahnawazKakarh/price-pulse-lahore.git
cd price-pulse-lahore
chmod +x setup.sh && ./setup.sh
```

### Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Description | Required |
|---|---|---|
| `GEMINI_API_KEY` | Google AI Studio API key | ✅ |
| `DATABASE_URL` | PostgreSQL connection string (Supabase or local) | Production |
| `TELEGRAM_BOT_TOKEN` | For failure alerts | Optional |
| `TELEGRAM_CHAT_ID` | For failure alerts | Optional |
| `TEST_MODE` | `true` = scrape 1 category only (dev), `false` = all 4 (prod) | Optional |

---

## Running Locally

```bash
source venv/bin/activate

# Run the daily pipeline (scrape → OCR → save)
python scraper/pipeline.py

# Start the API
uvicorn api.main:app --reload --port 8000

# Open the UI locally (API must be running)
open docs/index.html

# Open API docs
open http://localhost:8000/docs

# Open live GitHub Pages UI
open https://shahnawazkakarh.github.io/price-pulse-lahore

# Seed database from existing JSON files
python seed_db.py

# Force re-scrape (clears processed image cache)
find data/images/ -name "*.processed" -delete && python scraper/pipeline.py
```

---

## API Endpoints

### Prices

| Endpoint | Description |
|---|---|
| `GET /` | API info |
| `GET /health` | Health check — DB status, latest data date |
| `GET /today` | All prices today (`?category=vegetables\|fruits\|poultry\|essential_commodities`) |
| `GET /movers` | Top gainers and losers |
| `GET /categories` | Summary stats per category |
| `GET /search?q=tomato` | Search by name in English or Urdu |
| `GET /item/{slug}` | Single item — current price |
| `GET /item/{slug}/history` | Price history over time |

### Analytics & ML

| Endpoint | Description | Phase |
|---|---|---|
| `GET /analytics/summary` | Market inflation signal per category | ✅ Live |
| `GET /analytics/anomalies` | Items with unusual price movements | ✅ Live |
| `GET /analytics/forecast/{slug}` | 7-day price forecast | ✅ Live |
| `GET /analytics/inflation-index` | Lahore market price index over time | ✅ Live |

Full interactive docs at [price-pulse-lahore.vercel.app/docs](https://price-pulse-lahore.vercel.app/docs)

---

## Deployment

### API — Vercel

1. Import `ShahnawazKakarh/price-pulse-lahore` from [vercel.com](https://vercel.com)
2. Framework: **Other**
3. Add environment variables: `GEMINI_API_KEY`, `DATABASE_URL`, `ENV=production`
4. Deploy — auto-redeploys on every `git push`

### Database — Supabase

1. Create project at [supabase.com](https://supabase.com)
2. Use the **Transaction pooler** connection string (port 6543) as `DATABASE_URL`
3. Run `python -m db.database` to initialise tables
4. Run `python seed_db.py` to load existing data

### Cron Job — GitHub Actions

Runs automatically every day. Trigger manually from:
**GitHub → Actions → Daily Price Pipeline → Run workflow**

Add repository secrets: `GEMINI_API_KEY`, `DATABASE_URL`

---

## Tech Stack

| Layer | Technology |
|---|---|
| Scraper | Python 3.12, httpx, BeautifulSoup4 |
| AI OCR | Google Gemini 2.5 Flash Vision |
| Database | PostgreSQL via Supabase |
| ORM | SQLAlchemy + Alembic |
| API | FastAPI, uvicorn, slowapi |
| Fuzzy matching | rapidfuzz |
| Alerts | Telegram Bot API |
| Frontend | Vanilla JS + Chart.js, GitHub Pages |
| Cron | GitHub Actions |
| API Hosting | Vercel |

---

## Data Source

Official daily market rates published by the **Government of Punjab, Lahore**.
[lahore.punjab.gov.pk/market_rates](https://lahore.punjab.gov.pk/market_rates)

Prices are extracted from government-published JPEG images using AI Vision OCR and stored as structured records updated daily.

---

**Built by [Shahnawaz Khan](https://skakarh.com) · QA Pulse by SK**
