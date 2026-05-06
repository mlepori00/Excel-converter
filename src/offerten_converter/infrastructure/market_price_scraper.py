"""Infrastructure: market price lookup via toppreise.ch (Scrapling)."""

from __future__ import annotations

import asyncio
import re
import sys
from typing import Optional

from offerten_converter.application.ports import MarketPricePort

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

_SEARCH_URL = "https://www.toppreise.ch/produktsuche?q={ean}"


def _parse_price(text: str) -> Optional[float]:
    cleaned = text.replace("'", "").replace("\xa0", "").strip()
    match = re.search(r"(\d+)[.,](\d{2})", cleaned)
    if match:
        return float(f"{match.group(1)}.{match.group(2)}")
    return None


class ToppreiseScraper(MarketPricePort):
    """Fetches the lowest market price for an EAN from toppreise.ch."""

    def fetch_price(self, ean: str) -> Optional[float]:
        try:
            from scrapling.fetchers import StealthyFetcher
        except ImportError:
            return None

        try:
            page = StealthyFetcher.fetch(
                _SEARCH_URL.format(ean=ean), headless=True, network_idle=True
            )
            if page is None:
                return None

            page_text = page.get_all_text(ignore_tags=["script", "style"])
            if "Keine Treffer" in page_text and "0 Treffer" in page_text:
                return None

            prices = [
                _parse_price(n.text)
                for n in page.css(".priceContainer.productPrice .Plugin_Price")
            ]
            prices = [p for p in prices if p and p > 0]
            return min(prices) if prices else None

        except Exception:
            return None
