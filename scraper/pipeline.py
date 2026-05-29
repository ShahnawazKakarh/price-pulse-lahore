"""
Price Pulse Lahore — Daily Pipeline
Orchestrates: Scraper → OCR → DB → Alerts
Run this as a cron job on Railway at 7:30am PKT daily.
QA Pulse by SK · skakarh.com
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.scraper import run_scraper
from scraper.ocr import process_all_images
from alerts.telegram import alert_scrape_failure, alert_ocr_failure, alert_success

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def run_pipeline():
    """Full daily pipeline."""
    start = datetime.utcnow()
    logger.info("━" * 60)
    logger.info("  PRICE PULSE LAHORE — DAILY PIPELINE")
    logger.info(f"  Started: {start.isoformat()} UTC")
    logger.info("━" * 60)

    # ── Step 1: Scrape ────────────────────────────────────────────────────────
    scraped_images, scrape_failures = run_scraper()

    if scrape_failures:
        alert_scrape_failure(scrape_failures)

    if not scraped_images:
        logger.error("No images scraped — pipeline aborted")
        return

    # ── Step 2: OCR ───────────────────────────────────────────────────────────
    price_records, ocr_failures = process_all_images(scraped_images)

    if ocr_failures:
        alert_ocr_failure(ocr_failures)

    if not price_records:
        logger.error("No price records extracted — pipeline aborted")
        return

    # ── Step 3: Save to JSON (DB in Week 2) ───────────────────────────────────
    import json
    from pathlib import Path

    output_dir = Path(__file__).parent.parent / "data" / "daily"
    output_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    output_file = output_dir / f"{date_str}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(price_records, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(price_records)} records → {output_file}")

    # ── Step 4: Alert success ─────────────────────────────────────────────────
    categories = list({r["category"] for r in price_records})
    alert_success(len(price_records), categories)

    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info(f"Pipeline complete in {elapsed:.1f}s")
    logger.info("━" * 60)


if __name__ == "__main__":
    run_pipeline()
