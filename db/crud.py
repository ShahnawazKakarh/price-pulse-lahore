"""
Price Pulse Lahore — Database Operations (CRUD)
All read/write logic for items, price_readings, scrape_logs.
QA Pulse by SK · skakarh.com
"""

import json
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

from rapidfuzz import fuzz, process
from sqlalchemy import text, func
from sqlalchemy.orm import Session

from db.models import Item, PriceReading, ScrapeLog

logger = logging.getLogger(__name__)


# ── Item helpers ───────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    """Convert 'Tomato (A Grade)' → 'tomato-a-grade'"""
    name = name.lower().strip()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s_]+", "-", name)
    return name.strip("-")


def get_or_create_item(db: Session, name_english: str, name_urdu: str, category: str, unit: str) -> Item:
    """
    Find existing item by fuzzy name match or create a new one.
    This prevents duplicate items from OCR variations ("Tomato", "Tamatar", "Tomatoes").
    """
    slug = slugify(name_english)

    # 1. Exact slug match first
    item = db.query(Item).filter(Item.slug == slug).first()
    if item:
        return item

    # 2. Fuzzy match against all active items in same category
    all_items = db.query(Item).filter(
        Item.category == category,
        Item.is_active == True
    ).all()

    if all_items:
        names = [i.name_english for i in all_items]
        match = process.extractOne(name_english, names, scorer=fuzz.token_sort_ratio)

        if match and match[1] >= 85:  # 85% similarity threshold
            matched_item = next(i for i in all_items if i.name_english == match[0])
            logger.debug(f"Fuzzy matched '{name_english}' → '{matched_item.name_english}' ({match[1]}%)")

            # Add this name as an alias if not already present
            aliases = json.loads(matched_item.aliases or "[]")
            if name_english not in aliases and name_english != matched_item.name_english:
                aliases.append(name_english)
                matched_item.aliases = json.dumps(aliases)

            return matched_item

    # 3. Create new item
    item = Item(
        slug=slug,
        name_english=name_english,
        name_urdu=name_urdu or "",
        category=category,
        unit=unit,
        aliases=json.dumps([]),
    )
    db.add(item)
    db.flush()  # get the ID without committing
    logger.info(f"Created new item: {name_english} ({category})")
    return item


# ── Price reading helpers ──────────────────────────────────────────────────────

def get_previous_reading(db: Session, item_id: int, before_date: datetime) -> Optional[PriceReading]:
    """Get the most recent price reading for an item before a given date."""
    return (
        db.query(PriceReading)
        .filter(
            PriceReading.item_id == item_id,
            PriceReading.date < before_date,
        )
        .order_by(PriceReading.date.desc())
        .first()
    )


def get_7day_avg(db: Session, item_id: int, before_date: datetime) -> Optional[float]:
    """Compute 7-day rolling average for an item up to (not including) before_date."""
    since = before_date - timedelta(days=7)
    result = db.query(func.avg(PriceReading.avg_price)).filter(
        PriceReading.item_id == item_id,
        PriceReading.date >= since,
        PriceReading.date < before_date,
    ).scalar()
    return float(result) if result else None


def compute_direction(change_pct: Optional[float]) -> str:
    """Classify price movement."""
    if change_pct is None:
        return "stable"
    if change_pct > 1.0:
        return "up"
    if change_pct < -1.0:
        return "down"
    return "stable"


def upsert_price_reading(db: Session, item: Item, record: dict) -> PriceReading:
    """
    Insert or update a price reading for a given item and date.
    Pre-computes change fields on write.
    """
    date_str = record.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    reading_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    min_price = int(record.get("min_price", 0))
    max_price = int(record.get("max_price", 0))
    avg_price = (min_price + max_price) / 2.0

    # Check if reading already exists for this item+date
    existing = db.query(PriceReading).filter(
        PriceReading.item_id == item.id,
        PriceReading.date == reading_date,
    ).first()

    if existing:
        # Update prices if they changed
        existing.min_price = min_price
        existing.max_price = max_price
        existing.avg_price = avg_price
        reading = existing
    else:
        reading = PriceReading(
            item_id=item.id,
            date=reading_date,
            min_price=min_price,
            max_price=max_price,
            avg_price=avg_price,
            quality=record.get("quality", ""),
            source_url=record.get("source_url", ""),
            scraped_at=datetime.now(timezone.utc),
        )
        db.add(reading)

    # Compute change vs previous reading
    prev = get_previous_reading(db, item.id, reading_date)
    if prev and prev.avg_price > 0:
        reading.prev_avg_price = prev.avg_price
        reading.price_change = avg_price - prev.avg_price
        reading.price_change_pct = ((avg_price - prev.avg_price) / prev.avg_price) * 100
        reading.direction = compute_direction(reading.price_change_pct)
    else:
        reading.prev_avg_price = None
        reading.price_change = None
        reading.price_change_pct = None
        reading.direction = "stable"

    # Compute 7-day rolling average
    reading.avg_7d = get_7day_avg(db, item.id, reading_date)

    db.flush()
    return reading


# ── Bulk save ──────────────────────────────────────────────────────────────────

def save_price_records(db: Session, records: list[dict]) -> int:
    """
    Save all OCR-extracted price records to the database.
    Returns count of successfully saved records.
    """
    saved = 0
    for record in records:
        try:
            item = get_or_create_item(
                db=db,
                name_english=record["name_english"],
                name_urdu=record.get("name_urdu", ""),
                category=record["category"],
                unit=record.get("unit", "kg"),
            )
            upsert_price_reading(db, item, record)
            saved += 1
        except Exception as e:
            logger.error(f"Failed to save record {record.get('name_english')}: {e}")
            continue

    logger.info(f"Saved {saved}/{len(records)} records to database")
    return saved


# ── Scrape log ─────────────────────────────────────────────────────────────────

def log_scrape_run(
    db: Session,
    status: str,
    categories_ok: list,
    categories_fail: list,
    images_scraped: int,
    records_extracted: int,
    duration_seconds: float,
    error_message: str = None,
) -> ScrapeLog:
    log = ScrapeLog(
        status=status,
        categories_ok=json.dumps(categories_ok),
        categories_fail=json.dumps(categories_fail),
        images_scraped=images_scraped,
        records_extracted=records_extracted,
        duration_seconds=duration_seconds,
        error_message=error_message,
    )
    db.add(log)
    db.flush()
    return log


# ── API query helpers ──────────────────────────────────────────────────────────

def get_today_prices(db: Session, category: str = None) -> list[dict]:
    """Get all price readings for the most recent date."""
    # Find latest date in DB
    latest_date = db.query(func.max(PriceReading.date)).scalar()
    if not latest_date:
        return []

    query = (
        db.query(PriceReading, Item)
        .join(Item, PriceReading.item_id == Item.id)
        .filter(PriceReading.date == latest_date)
    )

    if category:
        query = query.filter(Item.category == category)

    results = query.order_by(Item.name_english).all()

    return [
        {
            "id":               item.id,
            "slug":             item.slug,
            "name_english":     item.name_english,
            "name_urdu":        item.name_urdu,
            "category":         item.category,
            "unit":             item.unit,
            "min_price":        reading.min_price,
            "max_price":        reading.max_price,
            "avg_price":        reading.avg_price,
            "price_change":     reading.price_change,
            "price_change_pct": reading.price_change_pct,
            "direction":        reading.direction,
            "avg_7d":           reading.avg_7d,
            "date":             reading.date.strftime("%Y-%m-%d"),
        }
        for reading, item in results
    ]


def get_top_movers(db: Session, limit: int = 10) -> dict:
    """Get biggest price gainers and losers for today."""
    today = get_today_prices(db)
    with_change = [p for p in today if p["price_change_pct"] is not None]

    gainers = sorted(with_change, key=lambda x: x["price_change_pct"], reverse=True)[:limit]
    losers  = sorted(with_change, key=lambda x: x["price_change_pct"])[:limit]

    return {"gainers": gainers, "losers": losers}


def get_item_history(db: Session, slug: str, days: int = 30) -> list[dict]:
    """Get price history for a single item."""
    item = db.query(Item).filter(Item.slug == slug).first()
    if not item:
        return []

    since = datetime.now(timezone.utc) - timedelta(days=days)
    readings = (
        db.query(PriceReading)
        .filter(
            PriceReading.item_id == item.id,
            PriceReading.date >= since,
        )
        .order_by(PriceReading.date.asc())
        .all()
    )

    return [
        {
            "date":             r.date.strftime("%Y-%m-%d"),
            "min_price":        r.min_price,
            "max_price":        r.max_price,
            "avg_price":        r.avg_price,
            "price_change_pct": r.price_change_pct,
            "direction":        r.direction,
        }
        for r in readings
    ]
