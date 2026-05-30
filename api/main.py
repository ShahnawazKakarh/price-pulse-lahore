"""
Price Pulse Lahore — FastAPI Application
QA Pulse by SK · skakarh.com
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv
from api.analytics import router as analytics_router

load_dotenv()

logger = logging.getLogger(__name__)

# ── Rate limiter ───────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── App lifespan ───────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Price Pulse Lahore API starting...")
    yield
    logger.info("Price Pulse Lahore API shutting down...")


# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Price Pulse Lahore — API",
    description=(
        "Live daily market rates for Lahore — vegetables, fruits, "
        "poultry & essential commodities. "
        "Data sourced from Punjab Government official rate lists.\n\n"
        "Built by [QA Pulse by SK](https://skakarh.com)"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production when domain is set
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ── Rate limit handler ─────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(analytics_router)


# ── Data loader ────────────────────────────────────────────────────────────────
# Loads from DB if available, falls back to latest daily JSON file
def load_latest_data() -> list[dict]:
    """
    Load today's price data.
    Priority: PostgreSQL DB → latest JSON file in data/daily/
    """
    # Try DB first
    try:
        from db.database import check_connection, get_db
        from db.crud import get_today_prices
        if check_connection():
            with get_db() as db:
                return get_today_prices(db)
    except Exception as e:
        logger.warning(f"DB unavailable, falling back to JSON: {e}")

    # JSON fallback
    daily_dir = Path(__file__).parent.parent / "data" / "daily"
    if not daily_dir.exists():
        return []

    json_files = sorted(daily_dir.glob("*.json"), reverse=True)
    if not json_files:
        return []

    latest = json_files[0]
    logger.info(f"Loading from JSON: {latest.name}")
    with open(latest, encoding="utf-8") as f:
        return json.load(f)


def enrich_records(records: list[dict]) -> list[dict]:
    """Add computed fields if missing (for JSON fallback data)."""
    enriched = []
    for r in records:
        min_p = r.get("min_price", 0)
        max_p = r.get("max_price", 0)
        avg_p = (min_p + max_p) / 2.0
        enriched.append({
            **r,
            "avg_price":        avg_p,
            "price_change":     r.get("price_change"),
            "price_change_pct": r.get("price_change_pct"),
            "direction":        r.get("direction", "stable"),
            "avg_7d":           r.get("avg_7d"),
        })
    return enriched


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Info"])
async def root():
    return {
        "name":        "Price Pulse Lahore API",
        "version":     "1.0.0",
        "description": "Live daily market rates for Lahore, Pakistan",
        "built_by":    "QA Pulse by SK — skakarh.com",
        "endpoints": {
            "today":      "/today",
            "movers":     "/movers",
            "categories": "/categories",
            "search":     "/search?q=tomato",
            "history":    "/item/{slug}/history",
            "health":     "/health",
            "docs":       "/docs",
        },
    }


@app.get("/health", tags=["Info"])
async def health():
    """Health check endpoint for Railway."""
    db_status = "unavailable"
    try:
        from db.database import check_connection
        db_status = "connected" if check_connection() else "unavailable"
    except Exception:
        pass

    daily_dir = Path(__file__).parent.parent / "data" / "daily"
    json_files = sorted(daily_dir.glob("*.json"), reverse=True) if daily_dir.exists() else []
    latest_json = json_files[0].name if json_files else None

    return {
        "status":      "ok",
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "database":    db_status,
        "latest_data": latest_json,
    }


@app.get("/today", tags=["Prices"])
@limiter.limit("60/minute")
async def get_today(
    request: Request,
    category: str = Query(None, description="Filter by category: vegetables, fruits, poultry, essential_commodities"),
):
    """
    Get all price readings for today.
    Optionally filter by category.
    """
    records = load_latest_data()
    records = enrich_records(records)

    if category:
        records = [r for r in records if r.get("category") == category]
        if not records:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for category '{category}'. "
                       f"Valid: vegetables, fruits, poultry, essential_commodities"
            )

    return {
        "date":    records[0]["date"] if records else None,
        "count":   len(records),
        "data":    records,
    }


@app.get("/movers", tags=["Prices"])
@limiter.limit("60/minute")
async def get_movers(
    request: Request,
    limit: int = Query(10, ge=1, le=50, description="Number of items to return"),
):
    """
    Get biggest price movers today — top gainers and losers.
    Perfect for the ticker display.
    """
    records = load_latest_data()
    records = enrich_records(records)
    with_change = [r for r in records if r.get("price_change_pct") is not None]

    gainers = sorted(with_change, key=lambda x: x["price_change_pct"], reverse=True)[:limit]
    losers  = sorted(with_change, key=lambda x: x["price_change_pct"])[:limit]

    # All movers sorted by absolute change for ticker
    all_movers = sorted(
        with_change,
        key=lambda x: abs(x["price_change_pct"]),
        reverse=True
    )[:limit]

    return {
        "date":       records[0]["date"] if records else None,
        "gainers":    gainers,
        "losers":     losers,
        "all_movers": all_movers,
    }


@app.get("/categories", tags=["Prices"])
@limiter.limit("60/minute")
async def get_categories(request: Request):
    """
    Get summary stats per category.
    """
    records = load_latest_data()
    records = enrich_records(records)

    categories = {}
    for r in records:
        cat = r.get("category", "unknown")
        if cat not in categories:
            categories[cat] = {
                "category":    cat,
                "item_count":  0,
                "avg_price":   0,
                "rising":      0,
                "falling":     0,
                "stable":      0,
            }
        categories[cat]["item_count"] += 1
        categories[cat]["avg_price"] += r.get("avg_price", 0)

        direction = r.get("direction", "stable")
        if direction == "up":
            categories[cat]["rising"] += 1
        elif direction == "down":
            categories[cat]["falling"] += 1
        else:
            categories[cat]["stable"] += 1

    # Compute average price per category
    for cat in categories.values():
        if cat["item_count"] > 0:
            cat["avg_price"] = round(cat["avg_price"] / cat["item_count"], 2)

    return {
        "date":       records[0]["date"] if records else None,
        "categories": list(categories.values()),
    }


@app.get("/search", tags=["Prices"])
@limiter.limit("30/minute")
async def search(
    request: Request,
    q: str = Query(..., min_length=2, description="Search query (item name)"),
):
    """
    Search items by name (English or Urdu).
    """
    records = load_latest_data()
    records = enrich_records(records)

    q_lower = q.lower().strip()
    results = [
        r for r in records
        if q_lower in r.get("name_english", "").lower()
        or q_lower in r.get("name_urdu", "")
    ]

    return {
        "query":   q,
        "count":   len(results),
        "results": results,
    }


@app.get("/item/{slug}/history", tags=["Prices"])
@limiter.limit("30/minute")
async def get_item_history(
    request: Request,
    slug: str,
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
):
    """
    Get price history for a single item.
    Requires DB — returns current price only from JSON fallback.
    """
    try:
        from db.database import check_connection, get_db
        from db.crud import get_item_history
        if check_connection():
            with get_db() as db:
                history = get_item_history(db, slug, days)
                if not history:
                    raise HTTPException(status_code=404, detail=f"Item '{slug}' not found")
                return {"slug": slug, "days": days, "count": len(history), "history": history}
    except HTTPException:
        raise
    except Exception:
        pass

    # JSON fallback — can only return today's price
    records = load_latest_data()
    match = next((r for r in records if r.get("name_english", "").lower().replace(" ", "-") == slug), None)
    if not match:
        raise HTTPException(
            status_code=404,
            detail=f"Item '{slug}' not found. History requires database connection."
        )

    return {
        "slug":    slug,
        "days":    days,
        "note":    "Full history requires database. Showing today only.",
        "count":   1,
        "history": [match],
    }


@app.get("/item/{slug}", tags=["Prices"])
@limiter.limit("60/minute")
async def get_item(request: Request, slug: str):
    """Get current price for a single item by slug."""
    records = load_latest_data()
    records = enrich_records(records)

    match = next(
        (r for r in records
         if r.get("name_english", "").lower().replace(" ", "-") == slug
         or r.get("slug") == slug),
        None
    )

    if not match:
        raise HTTPException(status_code=404, detail=f"Item '{slug}' not found")

    return match
