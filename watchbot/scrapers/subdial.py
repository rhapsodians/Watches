from __future__ import annotations
import logging
import re
from watchbot.models import Listing, TargetWatch
from watchbot.scraper_base import BaseScraper

logger = logging.getLogger(__name__)


class SubdialScraper(BaseScraper):
    name = "subdial"
    _BASE = "https://subdial.com/buy?q={query}"

    def search(self, target: TargetWatch) -> list[Listing]:
        query = self._url_encode(target.reference)
        soup = self._fetch(self._BASE.format(query=query))
        if soup is None:
            return []
        return self._parse_listings(soup, target)

    def _parse_listings(self, soup, target: TargetWatch) -> list[Listing]:
        listings = []
        cards = soup.select("[class*='product'], [class*='listing'], article, li[class*='item']")
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
                url = "https://subdial.com" + url

            title_el = card.select_one("h2, h3, [class*='title']")
            title = title_el.get_text(strip=True) if title_el else full_text[:120]

            price_el = card.select_one("[class*='price']")
            price = self._parse_price(price_el.get_text(strip=True)) if price_el else None

            lid = re.sub(r"[^a-z0-9]", "", url)[-24:]

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
            logger.debug("subdial parse error: %s", e)
            return None
