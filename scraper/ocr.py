"""
Price Pulse Lahore — Gemini Vision OCR
Sends market rate images to Gemini Flash and extracts structured price data.
QA Pulse by SK · skakarh.com
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
import io

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

load_dotenv()

logger = logging.getLogger(__name__)

# New google-genai SDK
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# gemini-1.5-flash: free tier, 1500 req/day, excellent vision
MODEL_NAME = "gemini-1.5-flash"

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

Example output:
[
  {"name_urdu": "ٹماٹر", "name_english": "Tomato", "unit": "kg", "min_price": 80, "max_price": 120, "quality": "A"},
  {"name_urdu": "پیاز", "name_english": "Onion", "unit": "kg", "min_price": 60, "max_price": 80, "quality": ""}
]
"""


def image_bytes_to_pil(image_bytes: bytes) -> Image.Image:
    """Convert raw bytes to PIL Image."""
    return Image.open(io.BytesIO(image_bytes))


def extract_prices_from_image(
    image_bytes: bytes,
    category: str,
    source_url: str,
    scraped_at: str,
) -> list[dict]:
    """
    Send image to Gemini Vision and extract structured price data.
    Returns list of price records ready for DB insertion.
    """
    logger.info(f"[OCR] Processing {category} image via Gemini Flash")

    try:
        image = image_bytes_to_pil(image_bytes)

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[EXTRACTION_PROMPT, image],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=4096,
            ),
        )

        raw_text = response.text.strip()
        logger.debug(f"[OCR] Raw Gemini response ({len(raw_text)} chars)")

        # Strip any accidental markdown fences
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)
        raw_text = raw_text.strip()

        items = json.loads(raw_text)

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
        return records

    except json.JSONDecodeError as e:
        logger.error(f"[OCR] JSON parse failed for {category}: {e}")
        return []
    except Exception as e:
        logger.error(f"[OCR] Gemini API error for {category}: {e}")
        return []


def process_all_images(scraped_images: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Run OCR on all scraped images.
    Returns (all_price_records, failed_categories)
    """
    all_records = []
    failed = []

    for image_data in scraped_images:
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
