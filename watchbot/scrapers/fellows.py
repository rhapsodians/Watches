from __future__ import annotations
import logging
import re
from datetime import date
from watchbot.models import Listing, TargetWatch
from watchbot.scraper_base import BaseScraper

logger = logging.getLogger(__name__)


class FellowsScraper(BaseScraper):
    name = "fellows"
    _BASE = "https://www.fellows.co.uk/sell-or-buy/watches/?q={query}"

    def search(self, target: TargetWatch) -> list[Listing]:
        query = self._url_encode(target.reference)
        soup = self._fetch(self._BASE.format(query=query))
        if soup is None:
            return []
        return self._parse_listings(soup, target)

    def _parse_listings(self, soup, target: TargetWatch) -> list[Listing]:
        listings = []
        for lot in soup.select("[class*='lot'], [class*='product'], article, li[class*='item']"):
            try:
                full_text = lot.get_text(" ", strip=True)
                if not self._is_exact_ref_match(full_text, target):
                    continue
                link_el = lot.select_one("a[href]")
                if not link_el:
                    continue
                url = link_el.get("href", "")
                if not url.startswith("http"):
                    url = "https://www.fellows.co.uk" + url
                title_el = lot.select_one("h2, h3, [class*='title'], [class*='name']")
                title = title_el.get_text(strip=True) if title_el else full_text[:120]

                # Try to extract estimate range
                est_low, est_high = None, None
                est_match = re.search(r"£([\d,]+)\s*[-–]\s*£([\d,]+)", full_text)
                if est_match:
                    est_low = self._parse_price(est_match.group(1))
                    est_high = self._parse_price(est_match.group(2))

                price_el = lot.select_one("[class*='price'], [class*='estimate']")
                price = self._parse_price(price_el.get_text(strip=True)) if price_el and not est_low else None

                lid = re.sub(r"[^a-z0-9]", "", url)[-24:]
                listings.append(Listing(
                    source=self.name, listing_id=lid, url=url, title=title,
                    price_gbp=price, is_exact_ref_match=True,
                    has_full_set=self._detect_full_set(full_text),
                    is_auction=True,
                    estimate_low_gbp=est_low, estimate_high_gbp=est_high,
                ))
            except Exception as e:
                logger.debug("fellows parse error: %s", e)
        return listings
