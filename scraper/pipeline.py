"""
Price Pulse Lahore — Daily Pipeline
Orchestrates: Scraper → OCR → DB (saves per image, not at end)
QA Pulse by SK · skakarh.com
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.scraper import run_scraper
from scraper.ocr import extract_prices_from_image
from alerts.telegram import alert_scrape_failure, alert_success
from db.database import init_db, get_db, check_connection
from db.crud import save_price_records, log_scrape_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def save_records(records: list[dict], db_available: bool) -> int:
    """Save records to DB or JSON immediately after each image OCR."""
    if not records:
        return 0

    saved = 0
    if db_available:
        try:
            with get_db() as db:
                saved = save_price_records(db, records)
            logger.info(f"Saved {saved} records to Supabase")
        except Exception as e:
            logger.error(f"DB save failed: {e} — falling back to JSON")
            db_available = False

    if not db_available:
        # Save to date-specific JSON file
        by_date = {}
        for r in records:
            d = r.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
            if d not in by_date:
                by_date[d] = []
            by_date[d].append(r)

        output_dir = Path(__file__).parent.parent / "data" / "daily"
        output_dir.mkdir(parents=True, exist_ok=True)

        for date, date_records in by_date.items():
            output_file = output_dir / f"{date}.json"
            # Append to existing file if it exists
            existing = []
            if output_file.exists():
                with open(output_file, encoding="utf-8") as f:
                    try:
                        existing = json.load(f)
                    except Exception:
                        existing = []
            # Merge — avoid duplicates by name+date+category
            existing_keys = {
                (r.get("name_english"), r.get("date"), r.get("category"))
                for r in existing
            }
            new_records = [
                r for r in date_records
                if (r.get("name_english"), r.get("date"), r.get("category")) not in existing_keys
            ]
            merged = existing + new_records
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(merged, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(new_records)} new records → {output_file.name}")
        saved = len(records)

    return saved


def run_pipeline():
    start = datetime.now(timezone.utc)
    logger.info("━" * 60)
    logger.info("  PRICE PULSE LAHORE — DAILY PIPELINE")
    logger.info(f"  Started: {start.isoformat()} UTC")
    logger.info("━" * 60)

    # ── Step 1: DB connection check ───────────────────────────────────────────
    db_available = check_connection()
    if db_available:
        init_db()
        logger.info("Database ready")
    else:
        logger.warning("Database unavailable — will save to JSON fallback only")

    # ── Step 2: Scrape all images ─────────────────────────────────────────────
    scraped_images, scrape_failures = run_scraper()

    if scrape_failures:
        alert_scrape_failure(scrape_failures)

    if not scraped_images:
        logger.error("No images scraped — pipeline aborted")
        return

    # ── Step 3: OCR + Save per image ──────────────────────────────────────────
    # Save immediately after each image — quota cutoff won't lose data
    total_saved   = 0
    total_records = 0
    ocr_failures  = []
    dates_seen    = set()

    logger.info(f"Processing {len(scraped_images)} images — saving after each one")

    for i, image_data in enumerate(scraped_images, 1):
        category = image_data["category"]
        filename = image_data.get("filename", "")
        logger.info(f"[{i}/{len(scraped_images)}] OCR: {category} — {filename}")

        records = extract_prices_from_image(
            image_bytes=image_data["image_bytes"],
            category=category,
            source_url=image_data["source_url"],
            scraped_at=image_data["scraped_at"],
            filename=filename,
        )

        if records:
            saved = save_records(records, db_available)
            total_saved   += saved
            total_records += len(records)
            dates_seen.update(r["date"] for r in records)
        else:
            ocr_failures.append(f"{category}/{filename}")
            logger.warning(f"No records extracted for {category}/{filename}")

    # ── Step 4: Summary ───────────────────────────────────────────────────────
    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    dates_list = sorted(dates_seen, reverse=True)

    logger.info("━" * 60)
    logger.info(f"Pipeline complete in {elapsed:.1f}s")
    logger.info(f"Total records extracted: {total_records}")
    logger.info(f"Total records saved:     {total_saved}")
    logger.info(f"Dates covered:           {dates_list}")
    if ocr_failures:
        logger.warning(f"OCR failures ({len(ocr_failures)}): {ocr_failures}")
    logger.info("━" * 60)

    # ── Step 5: Log to DB ─────────────────────────────────────────────────────
    if db_available and total_saved > 0:
        try:
            with get_db() as db:
                categories_ok   = list({r.split("/")[0] for r in [f"{image_data['category']}/{image_data.get('filename','')}" for image_data in scraped_images] if r.split("/")[0] not in [f.split("/")[0] for f in ocr_failures]})
                log_scrape_run(
                    db,
                    status="success" if not ocr_failures else "partial",
                    categories_ok=categories_ok,
                    categories_fail=ocr_failures,
                    images_scraped=len(scraped_images),
                    records_extracted=total_saved,
                    duration_seconds=elapsed,
                )
        except Exception as e:
            logger.warning(f"Could not log scrape run: {e}")

    # ── Step 6: Alert ─────────────────────────────────────────────────────────
    if total_saved > 0:
        alert_success(total_saved, list({d: True for d in dates_list}.keys()))


if __name__ == "__main__":
    run_pipeline()
