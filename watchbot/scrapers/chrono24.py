from __future__ import annotations
import logging
import re
from watchbot.models import Listing, TargetWatch
from watchbot.scraper_base import BaseScraper

logger = logging.getLogger(__name__)


class Chrono24Scraper(BaseScraper):
    name = "chrono24"
    # Reference page URL: dots and hyphens stripped from ref, brand slug merged
    _BASE = "https://www.chrono24.co.uk/{brand}/ref-{ref}.htm"
    _SEARCH = "https://www.chrono24.co.uk/search/index.htm?query={query}&sortorder=1"

    def _ref_to_url(self, ref: str) -> str:
        return re.sub(r"[\s.\-/]", "", ref).lower()

    def search(self, target: TargetWatch) -> list[Listing]:
        brand_slug = self._get_brand_slug(target)
        ref_slug = self._ref_to_url(target.reference)
        url = self._BASE.format(brand=brand_slug, ref=ref_slug)
        soup = self._fetch(url, wait_selector="article")
        if soup is None:
            # Fall back to keyword search with the reference number
            search_url = self._SEARCH.format(query=self._url_encode(target.reference))
            soup = self._fetch(search_url, wait_selector="article")
            if soup is None:
                return []
        return self._parse_listings(soup, target)

    def _parse_listings(self, soup, target: TargetWatch) -> list[Listing]:
        listings = []
        articles = soup.select("article.js-article-item, div.article-item, div[class*='article']")
        if not articles:
            articles = soup.select("[data-article-id]")
        for article in articles:
            listing = self._parse_article(article, target)
            if listing:
                listings.append(listing)
        return listings

    def _parse_article(self, article, target: TargetWatch) -> Listing | None:
        try:
            link_el = article.select_one("a[href*='/alangesoehne/'], a[href*='/cartier/'], a[href*='/omega/'], a[href*='/parmigianifleurier/'], a[href]")
            if not link_el:
                link_el = article.select_one("a")
            if not link_el:
                return None
            url = link_el.get("href", "")
            if not url.startswith("http"):
                url = "https://www.chrono24.co.uk" + url

            title_el = article.select_one("h2, .article-title, [class*='title']")
            title = title_el.get_text(strip=True) if title_el else article.get_text(" ", strip=True)[:120]

            full_text = article.get_text(" ", strip=True)
            if not self._is_exact_ref_match(full_text, target):
                return None

            price_el = article.select_one("[class*='price'], .article-price")
            price = self._parse_price(price_el.get_text(strip=True)) if price_el else None

            listing_id = re.search(r"id(\d+)", url)
            lid = listing_id.group(1) if listing_id else re.sub(r"[^a-z0-9]", "", url)[-20:]

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
            logger.debug("chrono24 parse error: %s", e)
            return None
