from __future__ import annotations
import logging
import re
from watchbot.models import Listing, TargetWatch
from watchbot.scraper_base import BaseScraper

logger = logging.getLogger(__name__)


class TheWatchCompanyScraper(BaseScraper):
    name = "thewatchcompany"
    _BASE = "https://www.thewatchcompany.com/search?q={query}"

    def search(self, target: TargetWatch) -> list[Listing]:
        query = self._url_encode(target.reference)
        soup = self._fetch(self._BASE.format(query=query))
        if soup is None:
            return []
        return self._parse_listings(soup, target)

    def _parse_listings(self, soup, target: TargetWatch) -> list[Listing]:
        listings = []
        for card in soup.select("[class*='product'], article, li[class*='item']"):
            try:
                full_text = card.get_text(" ", strip=True)
                if not self._is_exact_ref_match(full_text, target):
                    continue
                link_el = card.select_one("a[href]")
                if not link_el:
                    continue
                url = link_el.get("href", "")
                if not url.startswith("http"):
                    url = "https://www.thewatchcompany.com" + url
                title_el = card.select_one("h2, h3, [class*='title']")
                title = title_el.get_text(strip=True) if title_el else full_text[:120]
                price_el = card.select_one("[class*='price']")
                price = self._parse_price(price_el.get_text(strip=True)) if price_el else None
                lid = re.sub(r"[^a-z0-9]", "", url)[-24:]
                listings.append(Listing(source=self.name, listing_id=lid, url=url,
                                        title=title, price_gbp=price, is_exact_ref_match=True,
                                        has_full_set=self._detect_full_set(full_text)))
            except Exception as e:
                logger.debug("thewatchcompany parse error: %s", e)
        return listings
