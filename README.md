# Price Pulse Lahore

> Live daily market rates for Lahore — vegetables, fruits, poultry & commodities.  
> Powered by AI Vision OCR · Built by [QA Pulse by SK](https://skakarh.com)

[![Live UI](https://img.shields.io/badge/Live-GitHub%20Pages-blue)](https://shahnawazkakarh.github.io/price-pulse-lahore)
[![API](https://img.shields.io/badge/API-FastAPI-green)](https://price-pulse-lahore.up.railway.app/docs)
[![Data Source](https://img.shields.io/badge/Data-Punjab%20Gov-orange)](https://lahore.punjab.gov.pk/market_rates)

---

## What is this?

**Price Pulse Lahore** automatically scrapes the official Punjab Government daily market rate JPEGs, extracts structured price data using Google Gemini Vision AI, stores it in a time-series database, and serves it via a REST API with a live ticker UI.

People of Lahore can check today's prices, see what went up or down, and track trends — without navigating government websites.

## Features (Roadmap)

- [x] Automated daily scraper (runs at 7:30am PKT)
- [x] AI Vision OCR — Gemini Flash extracts prices from government JPEGs
- [x] Failure alerts via Telegram
- [ ] PostgreSQL + TimescaleDB time-series storage (Week 2)
- [ ] REST API with FastAPI (Week 3)
- [ ] Live ticker UI on GitHub Pages (Week 4)
- [ ] Price trend charts (Phase 2)
- [ ] Price alerts / notifications (Phase 2)
- [ ] AI price forecasting (Phase 3)

## Project Structure

```
price-pulse-lahore/
├── scraper/
│   ├── scraper.py      # Fetches images from gov site
│   ├── ocr.py          # Gemini Vision extracts prices from images
│   └── pipeline.py     # Orchestrates daily run
├── api/                # FastAPI REST API (Week 3)
├── db/                 # Database models & migrations (Week 2)
├── alerts/
│   └── telegram.py     # Failure alerting
├── docs/               # GitHub Pages UI (Week 4)
├── data/               # Local image cache & daily JSON output
├── requirements.txt
└── .env.example
```

## Setup (Local Dev)

```bash
git clone https://github.com/ShahnawazKakarh/price-pulse-lahore.git
cd price-pulse-lahore

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Fill in GEMINI_API_KEY, DATABASE_URL, TELEGRAM_BOT_TOKEN
```

### Run the pipeline manually

```bash
python scraper/pipeline.py
```

### Test Telegram alerts

```bash
python alerts/telegram.py
```

### Test OCR on a local image

```bash
python scraper/ocr.py path/to/rate_image.jpg vegetables
```

## Environment Variables

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio API key (free) |
| `DATABASE_URL` | PostgreSQL connection string |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for alerts |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |

## Data Source

Official daily market rates published by the **Government of Punjab, Lahore**.  
Source: [lahore.punjab.gov.pk/market_rates](https://lahore.punjab.gov.pk/market_rates)

---

**Built by [Shahnawaz Khan](https://skakarh.com) · QA Pulse by SK**
