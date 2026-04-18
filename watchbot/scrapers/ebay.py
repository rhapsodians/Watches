from __future__ import annotations
import logging
import re
from watchbot.models import Listing, TargetWatch
from watchbot.scraper_base import BaseScraper

logger = logging.getLogger(__name__)

# _sadis=2 = UK sellers only; _sacat=281 = Watches; LH_ItemCondition=3000 = Used
_URL = (
    "https://www.ebay.co.uk/sch/i.html"
    "?_nkw={query}&_sacat=281&LH_ItemCondition=3000&_sadis=2&_sop=10"
)


class EbayScraper(BaseScraper):
    name = "ebay"

    def search(self, target: TargetWatch) -> list[Listing]:
        query = self._url_encode(f"{target.brand} {target.reference}")
        url = _URL.format(query=query)
        soup = self._fetch(url, wait_selector=".s-item")
        if soup is None:
            return []
        return self._parse_listings(soup, target)

    def _parse_listings(self, soup, target: TargetWatch) -> list[Listing]:
        listings = []
        for item in soup.select("li.s-item"):
            listing = self._parse_item(item, target)
            if listing:
                listings.append(listing)
        return listings

    def _parse_item(self, item, target: TargetWatch) -> Listing | None:
        try:
            title_el = item.select_one(".s-item__title")
            if not title_el:
                return None
            title = title_el.get_text(strip=True)
            if title.lower().startswith("shop on ebay"):
                return None

            link_el = item.select_one("a.s-item__link")
            if not link_el:
                return None
            url = link_el.get("href", "").split("?")[0]

            full_text = item.get_text(" ", strip=True)
            if not self._is_exact_ref_match(full_text, target):
                return None

            price_el = item.select_one(".s-item__price")
            price = self._parse_price(price_el.get_text(strip=True)) if price_el else None

            m = re.search(r"/itm/(\d+)", url)
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
            logger.debug("ebay parse error: %s", e)
            return None
