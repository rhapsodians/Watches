from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class TargetWatch:
    brand: str
    model: str
    reference: str
    aliases: list[str] = field(default_factory=list)
    prefer_full_set: bool = False


@dataclass
class Listing:
    source: str
    listing_id: str
    url: str
    title: str
    price_gbp: float | None = None
    condition: str | None = None
    image_url: str | None = None
    is_exact_ref_match: bool = False
    has_full_set: bool | None = None
    is_auction: bool = False
    estimate_low_gbp: float | None = None
    estimate_high_gbp: float | None = None
    auction_end_date: date | None = None
    scraped_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def dedup_key(self) -> str:
        return f"{self.source}::{self.listing_id}"

    @property
    def display_price(self) -> str:
        if self.is_auction:
            if self.estimate_low_gbp and self.estimate_high_gbp:
                return f"Est. £{self.estimate_low_gbp:,.0f}–£{self.estimate_high_gbp:,.0f}"
            return "Estimate TBC"
        if self.price_gbp:
            return f"£{self.price_gbp:,.0f}"
        return "POA"


@dataclass
class SearchResult:
    target: TargetWatch
    listings: list[Listing] = field(default_factory=list)
    new_listings: list[Listing] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    seen_listings: list[Listing] = field(default_factory=list)  # populated by reporter
