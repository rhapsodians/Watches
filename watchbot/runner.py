from __future__ import annotations
import logging
from watchbot.models import Listing, SearchResult, TargetWatch
from watchbot.scraper_base import BaseScraper
from watchbot.state import ListingStore

logger = logging.getLogger(__name__)


def build_scrapers(settings: dict) -> list[BaseScraper]:
    from watchbot.scrapers.chrono24 import Chrono24Scraper
    from watchbot.scrapers.ebay import EbayScraper
    from watchbot.scrapers.watchfinder import WatchfinderScraper
    from watchbot.scrapers.subdial import SubdialScraper
    from watchbot.scrapers.chronext import ChronextScraper
    from watchbot.scrapers.thewatchagency import TheWatchAgencyScraper
    from watchbot.scrapers.xupes import XupesScraper
    from watchbot.scrapers.watchbox import WatchBoxScraper
    from watchbot.scrapers.thewatchcompany import TheWatchCompanyScraper
    from watchbot.scrapers.jura import JuraScraper
    from watchbot.scrapers.watchclub import WatchClubScraper
    from watchbot.scrapers.watchcollectors import WatchCollectorsScraper
    from watchbot.scrapers.onaro import OnaroScraper
    from watchbot.scrapers.acollectedman import ACollectedManScraper
    from watchbot.scrapers.fellows import FellowsScraper
    from watchbot.scrapers.sothebys import SothebyScraper
    from watchbot.scrapers.watchtrader import WatchTraderScraper

    return [
        Chrono24Scraper(settings),
        EbayScraper(settings),
        WatchfinderScraper(settings),
        SubdialScraper(settings),
        ChronextScraper(settings),
        TheWatchAgencyScraper(settings),
        XupesScraper(settings),
        WatchBoxScraper(settings),
        TheWatchCompanyScraper(settings),
        JuraScraper(settings),
        WatchClubScraper(settings),
        WatchCollectorsScraper(settings),
        OnaroScraper(settings),
        ACollectedManScraper(settings),
        FellowsScraper(settings),
        SothebyScraper(settings),
        WatchTraderScraper(settings),
    ]


class SearchRunner:
    def __init__(self, scrapers: list[BaseScraper], store: ListingStore, dry_run: bool = False):
        self._scrapers = scrapers
        self._store = store
        self._dry_run = dry_run

    def run(self, targets: list[TargetWatch]) -> list[SearchResult]:
        results = []
        for target in targets:
            result = self._run_target(target)
            results.append(result)
        return results

    def _run_target(self, target: TargetWatch) -> SearchResult:
        all_listings: list[Listing] = []
        errors: list[str] = []
        seen_dedup: set[str] = set()

        for scraper in self._scrapers:
            try:
                listings = scraper.search(target)
                for listing in listings:
                    if listing.dedup_key not in seen_dedup:
                        seen_dedup.add(listing.dedup_key)
                        all_listings.append(listing)
                if listings:
                    logger.info("%s → %s: %d listing(s)", target.reference, scraper.name, len(listings))
                else:
                    logger.debug("%s → %s: 0 listings", target.reference, scraper.name)
            except Exception as e:
                msg = f"{scraper.name}: {e}"
                errors.append(msg)
                logger.error("Scraper error — %s", msg)

        new_listings = []
        for listing in all_listings:
            if self._store.is_new(listing):
                new_listings.append(listing)
            if not self._dry_run:
                self._store.mark_seen(listing, target.reference)

        return SearchResult(
            target=target,
            listings=all_listings,
            new_listings=new_listings,
            errors=errors,
        )
