"""Fetch live exchange rates from the European Central Bank (ECB).

The ECB publishes a free daily XML feed – no API key, no registration required.
Rates are EUR-based; we convert them to our internal format (1 CHF = X foreign).
"""

from __future__ import annotations

import logging
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

logger = logging.getLogger(__name__)

_ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
_ECB_NS = "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"
_TIMEOUT_SECONDS = 5


def fetch_ecb_rates() -> tuple[dict[str, float], str] | None:
    """Download ECB daily rates and convert to our format (1 CHF = X foreign).

    Returns (rates_dict, date_str) or None if the request fails.

    ECB publishes rates relative to EUR.  Our internal format uses CHF as base:
        our_rates[X] = ecb_rates[X] / ecb_rates[CHF]
    """
    try:
        with urllib.request.urlopen(_ECB_URL, timeout=_TIMEOUT_SECONDS) as resp:
            xml_bytes = resp.read()
    except Exception as exc:
        logger.warning("ECB rate fetch failed: %s", exc)
        return None

    try:
        root = ET.fromstring(xml_bytes)
        # Locate the Cube elements that carry currency/rate attributes
        ecb: dict[str, float] = {"EUR": 1.0}
        date_str = ""
        for cube in root.iter(f"{{{_ECB_NS}}}Cube"):
            if cube.attrib.get("time"):
                date_str = cube.attrib["time"]
            currency = cube.attrib.get("currency")
            rate_str = cube.attrib.get("rate")
            if currency and rate_str:
                try:
                    ecb[currency.upper()] = float(rate_str)
                except ValueError:
                    pass

        # CHF must be present to convert
        chf_in_eur = ecb.get("CHF")
        if not chf_in_eur:
            logger.warning("CHF not found in ECB feed.")
            return None

        # Convert: 1 CHF = (ecb[X] / ecb[CHF]) X
        rates: dict[str, float] = {
            currency: round(rate / chf_in_eur, 6)
            for currency, rate in ecb.items()
        }
        rates["CHF"] = 1.0  # ensure exact

        logger.info("ECB rates loaded for %s (%d currencies).", date_str, len(rates))
        return rates, date_str

    except Exception as exc:
        logger.warning("ECB XML parse failed: %s", exc)
        return None
