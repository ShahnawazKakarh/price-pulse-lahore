"""
Price Pulse Lahore — Daily Pipeline
Orchestrates: Scraper → OCR → DB → Alerts
Run as a cron job on Railway at 7:30am PKT (2:30am UTC) daily.
QA Pulse by SK · skakarh.com
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.scraper import run_scraper
from scraper.ocr import process_all_images
from alerts.telegram import alert_scrape_failure, alert_ocr_failure, alert_success
from db.database import init_db, get_db, check_connection
from db.crud import save_price_records, log_scrape_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


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

    # ── Step 2: Scrape ────────────────────────────────────────────────────────
    scraped_images, scrape_failures = run_scraper()

    if scrape_failures:
        alert_scrape_failure(scrape_failures)

    if not scraped_images:
        logger.error("No images scraped — pipeline aborted")
        if db_available:
            with get_db() as db:
                log_scrape_run(
                    db, status="failed",
                    categories_ok=[], categories_fail=scrape_failures,
                    images_scraped=0, records_extracted=0,
                    duration_seconds=(datetime.now(timezone.utc) - start).total_seconds(),
                    error_message="No images scraped",
                )
        return

    # ── Step 3: OCR ───────────────────────────────────────────────────────────
    price_records, ocr_failures = process_all_images(scraped_images)

    if ocr_failures:
        alert_ocr_failure(ocr_failures)

    if not price_records:
        logger.error("No price records extracted — pipeline aborted")
        if db_available:
            with get_db() as db:
                log_scrape_run(
                    db, status="failed",
                    categories_ok=[], categories_fail=ocr_failures,
                    images_scraped=len(scraped_images), records_extracted=0,
                    duration_seconds=(datetime.now(timezone.utc) - start).total_seconds(),
                    error_message="OCR returned no records",
                )
        return

    # ── Step 4: Save to database ──────────────────────────────────────────────
    saved_count = 0
    if db_available:
        with get_db() as db:
            saved_count = save_price_records(db, price_records)

            categories_ok = list({r["category"] for r in price_records})
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            status = "success" if not (scrape_failures or ocr_failures) else "partial"

            log_scrape_run(
                db,
                status=status,
                categories_ok=categories_ok,
                categories_fail=scrape_failures + ocr_failures,
                images_scraped=len(scraped_images),
                records_extracted=saved_count,
                duration_seconds=elapsed,
            )

        logger.info(f"Saved {saved_count} records to database")
    else:
        # JSON fallback when DB is not available (local dev without Postgres)
        import json
        from pathlib import Path
        output_dir = Path(__file__).parent.parent / "data" / "daily"
        output_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        output_file = output_dir / f"{date_str}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(price_records, f, ensure_ascii=False, indent=2)
        logger.info(f"DB unavailable — saved {len(price_records)} records → {output_file}")

    # ── Step 5: Alert success ─────────────────────────────────────────────────
    categories = list({r["category"] for r in price_records})
    total = saved_count if db_available else len(price_records)
    alert_success(total, categories)

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info(f"Pipeline complete in {elapsed:.1f}s")
    logger.info("━" * 60)


if __name__ == "__main__":
    run_pipeline()
