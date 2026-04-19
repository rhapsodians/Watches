from __future__ import annotations
import re
import time
import logging
from abc import ABC, abstractmethod
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from watchbot.models import Listing, TargetWatch

logger = logging.getLogger(__name__)

FULL_SET_TERMS = [
    "box and papers", "box & papers", "b&p", "full set",
    "complete set", "original papers", "with papers", "with box",
    "box, papers", "papers and box",
]

# Site-specific brand name slugs for brands with special characters
BRAND_SLUGS: dict[str, dict[str, str]] = {
    "A. Lange & Söhne": {
        "chrono24":        "alangesoehne",
        "watchfinder":     "A. Lange and Sohne",
        "chronext":        "a-lange+soehne",
        "thewatchagency":  "a-lange-sohne",
        "watchcollectors": "a-lange-sohne",
        "onaro":           "a-lange-sohne",
        "acollectedman":   "a-lange-sohne",
        "subdial":         "a-lange-sohne",
        "ebay":            "A Lange Sohne",
        "xupes":           "a-lange-sohne",
        "watchclub":       "a-lange-sohne",
    },
    "Parmigiani Fleurier": {
        "chrono24":       "parmigianifleurier",
        "watchfinder":    "Parmigiani Fleurier",
        "chronext":       "parmigiani-fleurier",
        "thewatchagency": "parmigiani-fleurier",
        "ebay":           "Parmigiani Fleurier",
    },
}


class BaseScraper(ABC):
    name: str = ""
    uses_playwright: bool = True

    def __init__(self, settings: dict):
        self._delay = settings.get("scraping", {}).get("request_delay_seconds", 3)
        self._timeout = settings.get("scraping", {}).get("request_timeout_seconds", 30)
        self._headless = settings.get("scraping", {}).get("playwright_headless", True)
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-GB,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        self._last_request_time: float = 0

    @abstractmethod
    def search(self, target: TargetWatch) -> list[Listing]:
        ...

    def _get_brand_slug(self, target: TargetWatch) -> str:
        slugs = BRAND_SLUGS.get(target.brand, {})
        if self.name in slugs:
            return slugs[self.name]
        return target.brand

    def _ref_to_url(self, ref: str) -> str:
        """Default: strip all separators. Override per scraper."""
        return re.sub(r"[\s.\-/]", "", ref).lower()

    def _is_exact_ref_match(self, text: str, target: TargetWatch) -> bool:
        """
        Build a separator-flexible regex from each reference/alias and search in the
        original text. Splits the reference on any separator (., -, space, /) into
        segments and rejoins with [\s.\-/]* so it matches all common dealer formats:
          511.12.39.21.99.002  →  also matches  51112392199002  and  511-12-39-21-99-002
          PFC905-1020001-100182  →  also matches  PFC9051020001100182
        Uses (?<![A-Za-z0-9]) / (?![A-Za-z0-9]) boundaries to avoid partial matches.
        """
        for ref in [target.reference] + target.aliases:
            segments = re.split(r"[\s.\-/]+", ref.strip())
            sep = r"[\s.\-/]*"
            inner = sep.join(re.escape(s) for s in segments if s)
            pattern = rf"(?<![A-Za-z0-9]){inner}(?![A-Za-z0-9])"
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _detect_full_set(self, text: str) -> bool | None:
        lower = text.lower()
        if any(t in lower for t in FULL_SET_TERMS):
            return True
        return None

    def _parse_price(self, raw: str) -> float | None:
        if not raw:
            return None
        # Find all £/$/€ X,XXX patterns — on pre-owned dealer sites the asking
        # price is always the lowest when a "was/now" or "RRP/our price" pair exists
        matches = re.findall(r"[£$€]\s*([\d,]+(?:\.\d{1,2})?)", raw)
        if matches:
            prices = []
            for m in matches:
                try:
                    prices.append(float(m.replace(",", "")))
                except ValueError:
                    pass
            if prices:
                return min(prices)
        # Fallback: strip non-numeric and parse
        cleaned = re.sub(r"[£$€,\s]", "", raw)
        cleaned = re.sub(r"[^\d.]", "", cleaned)
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None

    def _sleep(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._delay:
            time.sleep(self._delay - elapsed)
        self._last_request_time = time.time()

    def _get_html(self, url: str, params: dict | None = None) -> BeautifulSoup | None:
        self._sleep()
        try:
            resp = self._session.get(url, params=params, timeout=self._timeout)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            logger.warning("%s: GET %s failed: %s", self.name, url, e)
            return None

    def _get_html_playwright(self, url: str, wait_selector: str | None = None) -> BeautifulSoup | None:
        self._sleep()
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=self._headless)
                ctx = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    locale="en-GB",
                )
                page = ctx.new_page()
                page.goto(url, timeout=60_000)
                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=15_000)
                    except PWTimeout:
                        pass
                else:
                    page.wait_for_load_state("networkidle", timeout=20_000)
                html = page.content()
                browser.close()
            return BeautifulSoup(html, "lxml")
        except Exception as e:
            logger.warning("%s: Playwright GET %s failed: %s", self.name, url, e)
            return None

    def _fetch(self, url: str, wait_selector: str | None = None) -> BeautifulSoup | None:
        soup = self._get_html(url)
        if soup is None:
            soup = self._get_html_playwright(url, wait_selector)
        return soup

    def _url_encode(self, text: str) -> str:
        return quote_plus(text)
