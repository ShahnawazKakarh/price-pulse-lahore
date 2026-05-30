"""
Price Pulse Lahore — Seed Supabase from existing JSON
Loads data/daily/*.json files into Supabase database.
Run once: python seed_db.py
QA Pulse by SK · skakarh.com
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

from db.database import get_db, init_db, check_connection
from db.crud import save_price_records


def seed():
    if not check_connection():
        logger.error("Cannot connect to database. Check DATABASE_URL in .env")
        sys.exit(1)

    init_db()

    daily_dir = Path("data/daily")
    json_files = sorted(daily_dir.glob("*.json"))

    if not json_files:
        logger.error("No JSON files found in data/daily/")
        sys.exit(1)

    total = 0
    for json_file in json_files:
        logger.info(f"Loading {json_file.name}...")
        with open(json_file, encoding="utf-8") as f:
            records = json.load(f)

        with get_db() as db:
            saved = save_price_records(db, records)
            total += saved
            logger.info(f"  → {saved}/{len(records)} records saved")

    logger.info(f"\nDone! Total records seeded: {total}")


if __name__ == "__main__":
    seed()
