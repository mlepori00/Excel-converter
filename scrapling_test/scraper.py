"""
Scrapling test: EAN oder Produktname → Marktpreis via toppreise.ch / galaxus.ch
"""
from __future__ import annotations

import asyncio
import json
import sys
import re
import time
from dataclasses import dataclass
from typing import Optional, Literal

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

TOPPREISE_URL = "https://www.toppreise.ch/produktsuche?q={query}"
GALAXUS_URL   = "https://www.galaxus.ch/search?q={query}"
DELAY         = 2.5


@dataclass
class PriceResult:
    query: str                                        # was gesucht wurde (EAN oder Name)
    query_type: Literal["ean", "name"]               # wie gesucht wurde
    source: str
    status: str                                       # "found" | "not_found" | "error"
    product_name: Optional[str] = None               # gefundener Produktname
    price: Optional[float] = None                    # Produktpreis ex. Versand
    price_incl_ship: Optional[float] = None
    currency: str = "CHF"
    num_offers: Optional[int] = None
    product_url: Optional[str] = None
    error_message: Optional[str] = None


def _parse_price(text: str) -> Optional[float]:
    cleaned = text.replace("'", "").replace("\xa0", "").strip()
    match = re.search(r"(\d+)[.,](\d{2})", cleaned)
    if match:
        return float(f"{match.group(1)}.{match.group(2)}")
    return None


def _check_deps() -> Optional[str]:
    try:
        from scrapling.fetchers import StealthyFetcher  # noqa: F401
    except ImportError:
        return "scrapling nicht installiert → pip install scrapling[all]"
    try:
        import camoufox  # noqa: F401
    except ImportError:
        return "camoufox nicht installiert → pip install camoufox[geoip] && python -m camoufox fetch"
    return None


def _fetch_toppreise_page(query: str, query_type: Literal["ean", "name"]) -> PriceResult:
    """Gemeinsame Logik für EAN- und Name-Suche auf toppreise.ch."""
    import traceback as tb
    from scrapling.fetchers import StealthyFetcher

    result = PriceResult(query=query, query_type=query_type, source="toppreise.ch", status="error")

    try:
        page = StealthyFetcher.fetch(
            TOPPREISE_URL.format(query=query), headless=True, network_idle=True
        )
        if page is None:
            result.error_message = "Keine Antwort"
            return result

        page_text = page.get_all_text(ignore_tags=["script", "style"])

        if "Keine Treffer" in page_text and "0 Treffer" in page_text:
            result.status = "not_found"
            return result

        ex_prices = [_parse_price(n.text) for n in page.css(".priceContainer.productPrice .Plugin_Price")]
        ex_prices = [p for p in ex_prices if p and p > 0]
        incl_prices = [_parse_price(n.text) for n in page.css(".priceContainer.shippingPrice .Plugin_Price")]
        incl_prices = [p for p in incl_prices if p and p > 0]

        if not ex_prices and not incl_prices:
            result.status = "not_found"
            return result

        result.price = min(ex_prices) if ex_prices else None
        result.price_incl_ship = min(incl_prices) if incl_prices else None
        result.num_offers = len(ex_prices) or len(incl_prices)

        for node in page.css("[class*=name]"):
            t = node.text.strip()
            if t and len(t) > 5 and t not in ("Produktname", "Name"):
                result.product_name = t[:120]
                break

        for node in page.css("a"):
            href = node.attrib.get("href", "")
            if "produktdetail" in href or "produkt/" in href:
                result.product_url = href if href.startswith("http") else f"https://www.toppreise.ch{href}"
                break

        result.status = "found"

    except Exception:
        result.status = "error"
        result.error_message = tb.format_exc()

    return result


# ── Öffentliche Scraper-Funktionen ────────────────────────────────────────────

def scrape_toppreise_by_ean(ean: str) -> PriceResult:
    err = _check_deps()
    if err:
        return PriceResult(query=ean, query_type="ean", source="toppreise.ch",
                           status="error", error_message=err)
    return _fetch_toppreise_page(ean, "ean")


def scrape_toppreise_by_name(name: str) -> PriceResult:
    """Sucht nach Produktname statt EAN. Treffer sind unschärfer."""
    err = _check_deps()
    if err:
        return PriceResult(query=name, query_type="name", source="toppreise.ch",
                           status="error", error_message=err)
    return _fetch_toppreise_page(name, "name")


def scrape_toppreise(ean: Optional[str], name: Optional[str]) -> PriceResult:
    """
    Intelligente Auswahl: EAN wenn vorhanden (präzise), sonst Name (ungefähr).
    Gibt immer ein PriceResult zurück.
    """
    if ean and ean.strip():
        return scrape_toppreise_by_ean(ean.strip())
    elif name and name.strip():
        return scrape_toppreise_by_name(name.strip())
    return PriceResult(query="", query_type="name", source="toppreise.ch",
                       status="error", error_message="Weder EAN noch Name angegeben")


def scrape_galaxus(ean: str) -> PriceResult:
    import traceback as tb
    err = _check_deps()
    if err:
        return PriceResult(query=ean, query_type="ean", source="galaxus.ch",
                           status="error", error_message=err)

    from scrapling.fetchers import StealthyFetcher
    result = PriceResult(query=ean, query_type="ean", source="galaxus.ch", status="error")

    try:
        page = StealthyFetcher.fetch(GALAXUS_URL.format(query=ean), headless=True, network_idle=True)
        if page is None:
            result.error_message = "Keine Antwort"
            return result

        page_text = page.get_all_text(ignore_tags=["script", "style"])
        if "Nothing found" in page_text or "Keine Treffer" in page_text:
            result.status = "not_found"
            return result

        for script in page.css('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.text)
                if data.get("@type") == "Product":
                    result.product_name = data.get("name", "")[:120]
                    result.product_url = page.url.split("?")[0]
                    offers = data.get("offers", {})
                    price_val = offers.get("price")
                    if price_val:
                        result.price = float(price_val)
                        result.currency = offers.get("priceCurrency", "CHF")
                        result.status = "found"
                    break
            except Exception:
                pass

        if result.status != "found":
            result.status = "not_found"

    except Exception:
        result.status = "error"
        result.error_message = tb.format_exc()

    return result


SCRAPERS = {
    "toppreise.ch": scrape_toppreise_by_ean,
    "galaxus.ch":   scrape_galaxus,
}
