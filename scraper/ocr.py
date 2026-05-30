"""
Price Pulse Lahore — Gemini Vision OCR
Sends market rate images to Gemini Flash and extracts structured price data.
QA Pulse by SK · skakarh.com
"""

import json
import logging
import os
import re
import time
from datetime import datetime
import io

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

load_dotenv()

logger = logging.getLogger(__name__)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# gemini-2.5-flash — free tier: 20 RPD, 5 RPM
MODEL_NAME = "gemini-2.5-flash"

REQUEST_DELAY_SECONDS = 15  # 5 RPM = 1 per 12s

EXTRACTION_PROMPT = """
You are a data extraction assistant. This image is a daily market rate list
from Lahore, Pakistan published by the Punjab government.

Extract ALL items and their prices from this image.

Return ONLY a valid JSON array. No explanation, no markdown, no code fences.
Each object must have exactly these fields:
- "name_urdu": item name in Urdu (as shown in image, empty string if not present)
- "name_english": item name in English (translate/transliterate if needed)
- "unit": unit of measurement (kg, gram, litre, dozen, piece, maund, etc.)
- "min_price": minimum price as integer (0 if not shown)
- "max_price": maximum price as integer (same as min if only one price shown)
- "quality": quality grade if mentioned (A, B, C, or empty string)

Rules:
- Prices are in Pakistani Rupees (PKR)
- If a price range is shown (e.g. 80-100), min_price=80 max_price=100
- If only one price shown, set both min and max to that value
- Skip header rows, dates, and non-item rows
- Include every item you can read, even if partially visible
- Keep name_english SHORT — max 3 words

Example output:
[
  {"name_urdu": "ٹماٹر", "name_english": "Tomato", "unit": "kg", "min_price": 80, "max_price": 120, "quality": "A"},
  {"name_urdu": "پیاز", "name_english": "Onion", "unit": "kg", "min_price": 60, "max_price": 80, "quality": ""}
]
"""


def image_bytes_to_pil(image_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(image_bytes))


def safe_parse_json(raw_text: str) -> list | None:
    """Try to parse JSON, attempt repair if truncated."""
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        # Try to repair truncated JSON by closing open brackets
        try:
            # Find last complete object
            last_complete = raw_text.rfind("},")
            if last_complete > 0:
                repaired = raw_text[:last_complete + 1] + "]"
                return json.loads(repaired)
        except Exception:
            pass
        # Try closing just the array
        try:
            return json.loads(raw_text.rstrip(",") + "]")
        except Exception:
            pass
        return None


def extract_prices_from_image(
    image_bytes: bytes,
    category: str,
    source_url: str,
    scraped_at: str,
    retry_on_429: bool = True,
) -> list[dict]:
    logger.info(f"[OCR] Processing {category} via {MODEL_NAME}")

    try:
        image = image_bytes_to_pil(image_bytes)

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[EXTRACTION_PROMPT, image],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=8192,  # increased from 4096
            ),
        )

        raw_text = response.text.strip()
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)
        raw_text = raw_text.strip()

        items = safe_parse_json(raw_text)

        if items is None:
            logger.error(f"[OCR] JSON parse failed for {category}")
            logger.debug(f"[OCR] Raw: {raw_text[:200]}")
            return []

        if not isinstance(items, list):
            logger.error(f"[OCR] Expected list, got {type(items)}")
            return []

        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        records = []
        for item in items:
            if not item.get("name_english"):
                continue
            records.append({
                "name_urdu":    item.get("name_urdu", ""),
                "name_english": item["name_english"].strip().title(),
                "unit":         item.get("unit", "kg").lower(),
                "min_price":    int(item.get("min_price", 0)),
                "max_price":    int(item.get("max_price", 0)),
                "quality":      item.get("quality", ""),
                "category":     category,
                "date":         date_str,
                "source_url":   source_url,
                "scraped_at":   scraped_at,
            })

        logger.info(f"[OCR] Extracted {len(records)} items from {category}")
        time.sleep(REQUEST_DELAY_SECONDS)
        return records

    except Exception as e:
        err_str = str(e)
        if "429" in err_str and retry_on_429:
            retry_delay = 65
            match = re.search(r"retry in (\d+)", err_str)
            if match:
                retry_delay = int(match.group(1)) + 5
            logger.warning(f"[OCR] Rate limited — waiting {retry_delay}s before retry...")
            time.sleep(retry_delay)
            return extract_prices_from_image(
                image_bytes, category, source_url, scraped_at, retry_on_429=False
            )
        logger.error(f"[OCR] Gemini API error for {category}: {e}")
        return []


def process_all_images(scraped_images: list[dict]) -> tuple[list[dict], list[str]]:
    """Run OCR on all scraped images — 1 per category."""
    all_records = []
    failed = []

    seen_categories = set()
    images_to_process = []
    for image_data in scraped_images:
        cat = image_data["category"]
        if cat not in seen_categories:
            images_to_process.append(image_data)
            seen_categories.add(cat)

    logger.info(f"[OCR] Processing {len(images_to_process)} images (1 per category)")

    for image_data in images_to_process:
        category = image_data["category"]
        records = extract_prices_from_image(
            image_bytes=image_data["image_bytes"],
            category=category,
            source_url=image_data["source_url"],
            scraped_at=image_data["scraped_at"],
        )
        if records:
            all_records.extend(records)
        else:
            failed.append(category)

    logger.info(f"[OCR] Total records extracted: {len(all_records)}")
    return all_records, failed


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ocr.py <image_path> [category]")
        sys.exit(1)

    img_path = sys.argv[1]
    cat = sys.argv[2] if len(sys.argv) > 2 else "test"

    with open(img_path, "rb") as f:
        img_bytes = f.read()

    records = extract_prices_from_image(img_bytes, cat, "local_test", datetime.utcnow().isoformat())
    print(json.dumps(records, ensure_ascii=False, indent=2))
    print(f"\nTotal: {len(records)} items extracted")
