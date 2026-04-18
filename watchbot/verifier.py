from __future__ import annotations
import re
import sys
import logging
import requests
from bs4 import BeautifulSoup
from watchbot.models import TargetWatch

logger = logging.getLogger(__name__)

# Cartier prefixes that appear in brand URLs but not in dealer listings
_BRAND_URL_PREFIXES = {"Cartier": "CR"}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
}


def _strip_brand_prefix(brand: str, reference: str) -> str:
    """Remove brand-specific catalog prefixes that dealers don't use."""
    prefix = _BRAND_URL_PREFIXES.get(brand, "")
    if prefix and reference.upper().startswith(prefix):
        return reference[len(prefix):]
    return reference


def _normalise_ref(ref: str) -> str:
    return re.sub(r"[\s.\-/]", "", ref).upper()


def _fetch_chrono24_ref_page(brand: str, reference: str) -> dict | None:
    """Attempt to fetch the Chrono24 reference page for a given brand+reference."""
    # Build brand slug (simplified mapping)
    brand_slugs = {
        "Cartier": "cartier",
        "Omega": "omega",
        "A. Lange & Söhne": "alangesoehne",
        "Parmigiani Fleurier": "parmigianifleurier",
        "Rolex": "rolex",
        "Patek Philippe": "patekphilippe",
        "Audemars Piguet": "audemarspiguet",
    }
    slug = brand_slugs.get(brand, re.sub(r"[^a-z0-9]", "", brand.lower()))
    ref_slug = _normalise_ref(reference).lower()
    url = f"https://www.chrono24.co.uk/{slug}/ref-{ref_slug}.htm"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "lxml")
            title_el = soup.select_one("h1, [class*='model-title'], title")
            title = title_el.get_text(strip=True) if title_el else ""
            count_el = soup.select_one("[class*='result-count'], [class*='article-count']")
            count = count_el.get_text(strip=True) if count_el else "unknown"
            return {"url": url, "title": title, "listing_count": count}
    except Exception as e:
        logger.debug("Chrono24 fetch failed: %s", e)
    return None


def _resolve_retail_url(retail_url: str) -> tuple[str, str] | None:
    """
    Fetch a retail product page and extract brand + manufacturer reference.
    Returns (brand, reference) or None if unable to resolve.
    """
    try:
        resp = requests.get(retail_url, headers=_HEADERS, timeout=20)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        text = soup.get_text(" ", strip=True)

        # Look for common reference number patterns in the page text
        # Omega: 511.12.39.21.99.002
        # Parmigiani: PFC905-1020001-100182
        # Cartier: WGTA0091
        # Lange: 101.032
        patterns = [
            r"\b([A-Z]{2,4}[\d]{3,4}[-\.\s][\d]{6,7}[-\.\s][\d]{4,6})\b",  # PFC905-...
            r"\b([A-Z]{2,6}\d{4,6})\b",                                         # WGTA0091
            r"\b(\d{3}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{3})\b",                 # Omega 6-part
            r"\b(\d{3}\.\d{3})\b",                                               # Lange 101.032
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                return None, m.group(1)
    except Exception as e:
        logger.debug("Retail URL resolve failed: %s", e)
    return None


def verify_reference(brand: str, reference: str) -> None:
    """Interactive reference verification. Prints findings and asks for confirmation."""
    cleaned_ref = _strip_brand_prefix(brand, reference)
    if cleaned_ref != reference:
        print(f"\nNote: Stripped brand prefix → using '{cleaned_ref}' (dealers don't use '{reference}')")
        reference = cleaned_ref

    print(f"\nVerifying: {brand} — {reference}")
    print("─" * 60)

    info = _fetch_chrono24_ref_page(brand, reference)
    if info:
        print(f"Found on Chrono24: {info['title']}")
        print(f"URL: {info['url']}")
        print(f"Listings: {info['listing_count']}")
    else:
        print("⚠ Could not fetch Chrono24 reference page (site may be blocking requests).")
        print("  The reference will still be searched across all configured sites.")

    norm = _normalise_ref(reference)
    print(f"\nNormalised reference (for matching): {norm}")
    print(f"Auto-generated alias (no separators): {norm}")

    print("\nSuggested watches.yaml entry:")
    print(f"""  - brand: {brand}
    model: <fill in model name>
    reference: "{reference}"
    aliases:
      - "{norm}"
    prefer_full_set: false""")

    print("\n" + "─" * 60)
    answer = input("Does this look correct? Add to watches.yaml? [y/n]: ").strip().lower()
    if answer != "y":
        print("Aborted. Please check the reference and try again.")
        sys.exit(1)
    print("✓ Confirmed. Add the entry above to config/watches.yaml to start monitoring.")


def verify_from_url(retail_url: str) -> None:
    """Resolve a retail product URL to a manufacturer reference, then verify."""
    print(f"\nResolving retail URL: {retail_url}")
    result = _resolve_retail_url(retail_url)
    if result is None or result[1] is None:
        print("⚠ Could not automatically extract reference from that URL.")
        print("  Please provide brand and reference manually:")
        print("  python run.py verify --brand BRAND --ref REFERENCE")
        sys.exit(1)
    _, reference = result
    print(f"Detected reference: {reference}")
    brand = input("Confirm brand name: ").strip()
    verify_reference(brand, reference)
