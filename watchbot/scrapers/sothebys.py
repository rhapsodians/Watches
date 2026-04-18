from __future__ import annotations
import logging
import re
from watchbot.models import Listing, TargetWatch
from watchbot.scraper_base import BaseScraper

logger = logging.getLogger(__name__)


class SothebyScraper(BaseScraper):
    name = "sothebys"
    _BASE = "https://www.sothebys.com/en/buy?query={query}&currency=GBP&department=WATCHES"

    def search(self, target: TargetWatch) -> list[Listing]:
        query = self._url_encode(target.reference)
        soup = self._get_html_playwright(self._BASE.format(query=query), wait_selector="[class*='lot'], [class*='card']")
        if soup is None:
            return []
        return self._parse_listings(soup, target)

    def _parse_listings(self, soup, target: TargetWatch) -> list[Listing]:
        listings = []
        for lot in soup.select("[class*='lot'], [class*='card'], article"):
            try:
                full_text = lot.get_text(" ", strip=True)
                if not self._is_exact_ref_match(full_text, target):
                    continue
                link_el = lot.select_one("a[href]")
                if not link_el:
                    continue
                url = link_el.get("href", "")
                if not url.startswith("http"):
                    url = "https://www.sothebys.com" + url
                title_el = lot.select_one("h2, h3, [class*='title'], [class*='name']")
                title = title_el.get_text(strip=True) if title_el else full_text[:120]

                est_low, est_high = None, None
                est_match = re.search(r"£([\d,]+)\s*[-–]\s*£([\d,]+)", full_text)
                if est_match:
                    est_low = self._parse_price(est_match.group(1))
                    est_high = self._parse_price(est_match.group(2))

                lid = re.sub(r"[^a-z0-9]", "", url)[-28:]
                listings.append(Listing(
                    source=self.name, listing_id=lid, url=url, title=title,
                    is_exact_ref_match=True,
                    has_full_set=self._detect_full_set(full_text),
                    is_auction=True,
                    estimate_low_gbp=est_low, estimate_high_gbp=est_high,
                ))
            except Exception as e:
                logger.debug("sothebys parse error: %s", e)
        return listings
