from __future__ import annotations
import json
import logging
import re
from pathlib import Path
from watchbot.models import Listing, TargetWatch
from watchbot.scraper_base import BaseScraper

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://www.watchfinder.co.uk/search#q={query}"
_IDS_CACHE = "data/watchfinder_ids.json"


class WatchfinderScraper(BaseScraper):
    name = "watchfinder"

    def _ref_to_url(self, ref: str) -> str:
        return ref  # Watchfinder preserves dots in URLs

    def _load_id_cache(self) -> dict:
        path = Path(_IDS_CACHE)
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                pass
        return {}

    def search(self, target: TargetWatch) -> list[Listing]:
        cache = self._load_id_cache()
        model_id = cache.get(target.reference)

        if model_id:
            brand_slug = self._get_brand_slug(target)
            model_slug = target.model.replace(" ", "%20")
            ref_slug = self._ref_to_url(target.reference)
            url = (
                f"https://www.watchfinder.co.uk/"
                f"{self._url_encode(brand_slug)}/{self._url_encode(target.model)}"
                f"/{ref_slug}/{model_id}/watches"
            )
        else:
            query = self._url_encode(f"{target.brand} {target.reference}")
            url = f"https://www.watchfinder.co.uk/search#q={query}"

        soup = self._get_html_playwright(url, wait_selector=".product-card, .watches-list, main")
        if soup is None:
            return []
        return self._parse_listings(soup, target)

    def _parse_listings(self, soup, target: TargetWatch) -> list[Listing]:
        listings = []
        cards = soup.select(".product-card, [class*='product-item'], [class*='watch-card']")
        if not cards:
            cards = soup.select("article, li[class*='item']")
        for card in cards:
            listing = self._parse_card(card, target)
            if listing:
                listings.append(listing)
        return listings

    def _parse_card(self, card, target: TargetWatch) -> Listing | None:
        try:
            full_text = card.get_text(" ", strip=True)
            if not self._is_exact_ref_match(full_text, target):
                return None

            link_el = card.select_one("a[href]")
            if not link_el:
                return None
            url = link_el.get("href", "")
            if not url.startswith("http"):
                url = "https://www.watchfinder.co.uk" + url

            title_el = card.select_one("h2, h3, [class*='title'], [class*='name']")
            title = title_el.get_text(strip=True) if title_el else full_text[:120]

            price_el = card.select_one("[class*='price']")
            price = self._parse_price(price_el.get_text(strip=True)) if price_el else None

            m = re.search(r"/item/(\d+)", url)
            lid = m.group(1) if m else re.sub(r"[^a-z0-9]", "", url)[-20:]

            return Listing(
                source=self.name,
                listing_id=lid,
                url=url,
                title=title,
                price_gbp=price,
                is_exact_ref_match=True,
                has_full_set=self._detect_full_set(full_text),
            )
        except Exception as e:
            logger.debug("watchfinder parse error: %s", e)
            return None
