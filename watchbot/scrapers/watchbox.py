from __future__ import annotations
import json
import logging
import re
from watchbot.models import Listing, TargetWatch
from watchbot.scraper_base import BaseScraper

logger = logging.getLogger(__name__)


class WatchBoxScraper(BaseScraper):
    name = "watchbox"
    _BASE = "https://www.thewatchbox.com/gb/collections/all?q={query}&sort_by=created-descending"

    def search(self, target: TargetWatch) -> list[Listing]:
        query = self._url_encode(target.reference)
        soup = self._fetch(self._BASE.format(query=query))
        if soup is None:
            return []

        # Try structured JSON first (Shopify stores embed product data)
        listings = self._parse_json(soup, target)
        if not listings:
            listings = self._parse_html(soup, target)
        return listings

    def _parse_json(self, soup, target: TargetWatch) -> list[Listing]:
        listings = []
        for script in soup.select("script[type='application/json']"):
            try:
                data = json.loads(script.string or "")
                products = data if isinstance(data, list) else data.get("products", [])
                for p in products:
                    title = p.get("title", "")
                    full_text = title + " " + p.get("body_html", "")
                    if not self._is_exact_ref_match(full_text, target):
                        continue
                    handle = p.get("handle", "")
                    url = f"https://www.thewatchbox.com/gb/products/{handle}"
                    price = self._parse_price(str(p.get("price", "")))
                    lid = str(p.get("id", re.sub(r"[^a-z0-9]", "", handle)[-20:]))
                    listings.append(Listing(source=self.name, listing_id=lid, url=url,
                                            title=title, price_gbp=price,
                                            is_exact_ref_match=True,
                                            has_full_set=self._detect_full_set(full_text)))
            except Exception:
                continue
        return listings

    def _parse_html(self, soup, target: TargetWatch) -> list[Listing]:
        listings = []
        for card in soup.select("[class*='product'], article"):
            try:
                full_text = card.get_text(" ", strip=True)
                if not self._is_exact_ref_match(full_text, target):
                    continue
                link_el = card.select_one("a[href]")
                if not link_el:
                    continue
                url = link_el.get("href", "")
                if not url.startswith("http"):
                    url = "https://www.thewatchbox.com" + url
                title_el = card.select_one("h2, h3, [class*='title']")
                title = title_el.get_text(strip=True) if title_el else full_text[:120]
                price_el = card.select_one("[class*='price']")
                price = self._parse_price(price_el.get_text(strip=True)) if price_el else None
                lid = re.sub(r"[^a-z0-9]", "", url)[-24:]
                listings.append(Listing(source=self.name, listing_id=lid, url=url,
                                        title=title, price_gbp=price, is_exact_ref_match=True,
                                        has_full_set=self._detect_full_set(full_text)))
            except Exception as e:
                logger.debug("watchbox parse error: %s", e)
        return listings
