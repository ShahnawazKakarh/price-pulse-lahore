"""
Price Pulse Lahore — Scraper
Fetches daily market rate images from lahore.punjab.gov.pk
QA Pulse by SK · skakarh.com
"""

import hashlib
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

BASE_URL = os.getenv("SCRAPE_URL_BASE", "https://lahore.punjab.gov.pk")

# Known category pages — extend if the gov site adds more
CATEGORY_URLS = {
    "vegetables": f"{BASE_URL}/vegetables-rate-list",
    "fruits":     f"{BASE_URL}/fruit-rate-list",
    "poultry":    f"{BASE_URL}/poultry-rate-list",
    "commodities":f"{BASE_URL}/general-items-rate-list",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": BASE_URL,
}

# Local image cache dir — keeps downloaded JPEGs for audit trail
IMAGE_DIR = Path(__file__).parent.parent / "data" / "images"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def _hash_file(content: bytes) -> str:
    """SHA-256 hash of raw bytes — used for duplicate detection."""
    return hashlib.sha256(content).hexdigest()


def _already_downloaded(image_hash: str) -> bool:
    """Check if this exact image was already processed today."""
    marker = IMAGE_DIR / f"{image_hash}.processed"
    return marker.exists()


def _mark_downloaded(image_hash: str) -> None:
    """Mark image as processed so we skip it next run."""
    marker = IMAGE_DIR / f"{image_hash}.processed"
    marker.touch()


def fetch_page(url: str, retries: int = 3) -> str | None:
    """Fetch HTML from a URL with retry logic."""
    for attempt in range(1, retries + 1):
        try:
            with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=20) as client:
                r = client.get(url)
                if r.status_code == 200:
                    return r.text
                logger.warning(f"HTTP {r.status_code} on attempt {attempt} for {url}")
        except httpx.RequestError as e:
            logger.warning(f"Request error on attempt {attempt}: {e}")
        time.sleep(2 ** attempt)  # exponential backoff
    return None


def extract_image_urls(html: str, base_url: str) -> list[str]:
    """
    Parse HTML and extract all image URLs that look like rate list JPEGs.
    The gov site embeds them as <img> tags or links to JPEGs directly.
    """
    soup = BeautifulSoup(html, "html.parser")
    image_urls = []

    # Strategy 1: <img> tags with src pointing to rate images
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if any(kw in src.lower() for kw in ["rate", "price", "market", "list"]):
            full_url = src if src.startswith("http") else f"{base_url}/{src.lstrip('/')}"
            image_urls.append(full_url)

    # Strategy 2: <a> tags linking directly to JPEGs / PNGs
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith((".jpg", ".jpeg", ".png")):
            full_url = href if href.startswith("http") else f"{base_url}/{href.lstrip('/')}"
            image_urls.append(full_url)

    # Strategy 3: Any <img> inside content/article area (fallback)
    if not image_urls:
        content_area = soup.find(class_=lambda c: c and any(
            kw in c.lower() for kw in ["content", "main", "article", "body"]
        ))
        if content_area:
            for img in content_area.find_all("img"):
                src = img.get("src", "")
                if src:
                    full_url = src if src.startswith("http") else f"{base_url}/{src.lstrip('/')}"
                    image_urls.append(full_url)

    return list(dict.fromkeys(image_urls))  # deduplicate, preserve order


def download_image(url: str, category: str) -> tuple[bytes, str] | None:
    """
    Download an image. Returns (raw_bytes, local_path) or None on failure.
    Skips if already downloaded today (hash check).
    """
    try:
        with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30) as client:
            r = client.get(url)
            if r.status_code != 200:
                logger.warning(f"Failed to download image {url}: HTTP {r.status_code}")
                return None

            content = r.content
            image_hash = _hash_file(content)

            if _already_downloaded(image_hash):
                logger.info(f"[{category}] Image already processed (hash match), skipping.")
                return None

            # Save image with date + category in filename
            date_str = datetime.now().strftime("%Y-%m-%d")
            filename = IMAGE_DIR / f"{date_str}_{category}_{image_hash[:8]}.jpg"
            filename.write_bytes(content)
            _mark_downloaded(image_hash)

            logger.info(f"[{category}] Downloaded → {filename.name}")
            return content, str(filename)

    except Exception as e:
        logger.error(f"Error downloading {url}: {e}")
        return None


def scrape_category(category: str, url: str) -> list[dict]:
    """
    Full pipeline for one category:
    1. Fetch the page HTML
    2. Extract image URLs
    3. Download new images
    Returns list of {category, image_path, image_bytes, url, scraped_at}
    """
    logger.info(f"[{category}] Scraping {url}")
    results = []

    html = fetch_page(url)
    if not html:
        logger.error(f"[{category}] Could not fetch page — will trigger alert")
        return results

    image_urls = extract_image_urls(html, BASE_URL)
    logger.info(f"[{category}] Found {len(image_urls)} image(s)")

    if not image_urls:
        logger.warning(f"[{category}] No images found on page — site structure may have changed")

    for img_url in image_urls:
        result = download_image(img_url, category)
        if result:
            image_bytes, image_path = result
            results.append({
                "category":    category,
                "image_path":  image_path,
                "image_bytes": image_bytes,
                "source_url":  img_url,
                "scraped_at":  datetime.utcnow().isoformat(),
            })

    return results


def run_scraper() -> list[dict]:
    """
    Entry point — scrape all categories.
    Returns all successfully downloaded images ready for OCR.
    """
    logger.info("=" * 60)
    logger.info("Price Pulse Lahore — Daily Scrape Starting")
    logger.info(f"UTC: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)

    all_results = []
    failed_categories = []

    for category, url in CATEGORY_URLS.items():
        try:
            results = scrape_category(category, url)
            all_results.extend(results)
            if not results:
                failed_categories.append(category)
        except Exception as e:
            logger.error(f"[{category}] Unexpected error: {e}")
            failed_categories.append(category)

    logger.info(f"Scrape complete — {len(all_results)} image(s) downloaded")

    if failed_categories:
        logger.warning(f"Failed categories: {failed_categories}")

    return all_results, failed_categories


if __name__ == "__main__":
    results, failed = run_scraper()
    print(f"\nDone: {len(results)} images ready for OCR")
    if failed:
        print(f"Failed: {failed}")
