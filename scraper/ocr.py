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

REQUEST_DELAY_SECONDS = 15  # 5 RPM = 1 per 12s, using 15s to be safe

EXTRACTION_PROMPT = """
You are a data extraction assistant. This image is a daily market rate list
from Lahore, Pakistan published by the Punjab government.

IMPORTANT LAYOUT NOTE:
- The image has TWO columns of items side by side
- Each column has: item name (Urdu, right side) | Grade 1 price | Grade 2 price
- Read ALL items from BOTH the LEFT column and the RIGHT column completely
- Do NOT stop after reading one column — read every single row in both columns
- The date is printed at the top of the image in format DD/MM/YYYY — extract it

Extract ALL items and their prices from this image.

Return ONLY a valid JSON object with exactly this structure. No explanation, no markdown, no code fences:
{
  "date": "YYYY-MM-DD",
  "items": [
    {"name_urdu": "...", "name_english": "...", "unit": "...", "min_price": 0, "max_price": 0, "quality": ""},
    ...
  ]
}

Field rules:
- "date": extract from image header (format: YYYY-MM-DD). If not visible use null
- "name_urdu": item name exactly as shown in Urdu
- "name_english": English translation/transliteration of the item name
- "unit": kg / gram / litre / dozen / piece / maund / crate — infer from context
- "min_price": Grade 2 (دوئم) price as integer. 0 if shown as dash (-)
- "max_price": Grade 1 (اول) price as integer. Same as min if only one grade
- "quality": "A" for Grade 1 (اول), "B" for Grade 2 (دوئم), "" if no grade shown

Rules:
- Prices are in Pakistani Rupees (PKR)
- Include EVERY item you can read, even partially visible ones
- Skip only header rows and the date row
- If price shown as "-" set to 0
- Keep name_english SHORT — 3 words max
- Read the COMPLETE image — there may be 25-40 items total across both columns
"""


def image_bytes_to_pil(image_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(image_bytes))


def safe_parse_json(raw_text: str) -> dict | None:
    """Parse JSON response, attempt repair if truncated."""
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        # Try to repair truncated items array
        try:
            last_complete = raw_text.rfind("},")
            if last_complete > 0:
                repaired = raw_text[:last_complete + 1] + "]}"
                return json.loads(repaired)
        except Exception:
            pass
        # Try closing array and object
        try:
            return json.loads(raw_text.rstrip(",") + "]}")
        except Exception:
            pass
        return None


def extract_date_from_filename(filename: str) -> str | None:
    """
    Try to extract date from image filename.
    e.g. 'WhatsApp Image 2026-05-20 at 5.48.36 AM.jpeg' → '2026-05-20'
    """
    match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    if match:
        return match.group(1)
    return None


def extract_prices_from_image(
    image_bytes: bytes,
    category: str,
    source_url: str,
    scraped_at: str,
    filename: str = "",
    retry_on_429: bool = True,
) -> list[dict]:
    logger.info(f"[OCR] Processing {category} via {MODEL_NAME} — {filename}")

    try:
        image = image_bytes_to_pil(image_bytes)

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[EXTRACTION_PROMPT, image],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=16384,  # increased for dense two-column images
            ),
        )

        raw_text = response.text.strip()
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)
        raw_text = raw_text.strip()

        parsed = safe_parse_json(raw_text)

        if parsed is None:
            logger.error(f"[OCR] JSON parse failed for {category} — {filename}")
            return []

        # Extract date — priority: from image > from filename > today
        image_date = parsed.get("date")
        if not image_date:
            image_date = extract_date_from_filename(filename)
        if not image_date:
            image_date = datetime.utcnow().strftime("%Y-%m-%d")
            logger.warning(f"[OCR] Could not extract date from image or filename, using today: {image_date}")
        else:
            logger.info(f"[OCR] Date extracted: {image_date}")

        items = parsed.get("items", [])
        if not isinstance(items, list):
            logger.error(f"[OCR] Expected items list, got {type(items)}")
            return []

        # Validate item count — warn if suspiciously low
        if len(items) < 5:
            logger.warning(f"[OCR] Only {len(items)} items extracted from {category} — may be incomplete")
        elif len(items) < 15 and category in ["fruits", "vegetables"]:
            logger.warning(f"[OCR] Only {len(items)} items for {category} — expected 20+, may be missing items")
        else:
            logger.info(f"[OCR] Extracted {len(items)} items from {category} ✓")

        records = []
        for item in items:
            if not item.get("name_english"):
                continue
            min_p = int(item.get("min_price", 0) or 0)
            max_p = int(item.get("max_price", 0) or 0)
            # If only one price given, set both
            if max_p == 0 and min_p > 0:
                max_p = min_p
            if min_p == 0 and max_p > 0:
                min_p = max_p

            records.append({
                "name_urdu":    item.get("name_urdu", ""),
                "name_english": item["name_english"].strip().title(),
                "unit":         item.get("unit", "kg").lower(),
                "min_price":    min_p,
                "max_price":    max_p,
                "quality":      item.get("quality", ""),
                "category":     category,
                "date":         image_date,
                "source_url":   source_url,
                "scraped_at":   scraped_at,
            })

        logger.info(f"[OCR] Final: {len(records)} valid records for {category} on {image_date}")
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
                image_bytes, category, source_url, scraped_at,
                filename, retry_on_429=False
            )
        logger.error(f"[OCR] Gemini API error for {category}: {e}")
        return []


def process_all_images(scraped_images: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Run OCR on all scraped images.
    Each image may have a different date — all are processed.
    """
    all_records = []
    failed = []

    logger.info(f"[OCR] Processing {len(scraped_images)} images")

    for image_data in scraped_images:
        category = image_data["category"]
        filename = image_data.get("filename", "")
        records = extract_prices_from_image(
            image_bytes=image_data["image_bytes"],
            category=category,
            source_url=image_data["source_url"],
            scraped_at=image_data["scraped_at"],
            filename=filename,
        )
        if records:
            all_records.extend(records)
        else:
            failed.append(f"{category}/{filename}")

    # Summary by date
    dates_found = sorted(set(r["date"] for r in all_records))
    logger.info(f"[OCR] Total: {len(all_records)} records across {len(dates_found)} dates: {dates_found}")
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

    records = extract_prices_from_image(
        img_bytes, cat, "local_test",
        datetime.utcnow().isoformat(),
        filename=img_path.split("/")[-1]
    )
    print(json.dumps(records, ensure_ascii=False, indent=2))
    print(f"\nTotal: {len(records)} items extracted")
