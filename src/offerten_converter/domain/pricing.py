"""Pure domain functions for pricing, margin calculation, and currency conversion."""

from __future__ import annotations

DEFAULT_RATES: dict[str, float] = {
    # All rates relative to CHF (1 CHF = X foreign currency)
    "CHF": 1.0,
    "EUR": 0.955,
    "USD": 1.09,
    "GBP": 0.825,
    "SEK": 11.80,
    "NOK": 11.45,
    "DKK": 7.12,
    "JPY": 163.0,
    "CAD": 1.49,
    "AUD": 1.65,
}

MIN_MARGIN_WARNING = 0.20  # orange below this
MIN_MARGIN_ERROR = 0.10  # red below this


def convert_to_target(
    amount: float | None,
    from_currency: str,
    to_currency: str,
    rates: dict[str, float] | None = None,
) -> float | None:
    """Convert *amount* from *from_currency* to *to_currency* using static rates.

    Rates are expressed as "1 CHF = X foreign", so:
        CHF amount = foreign / rate_foreign
        target = chf_amount * rate_target
    """
    if amount is None:
        return None
    r = rates or DEFAULT_RATES
    from_rate = r.get(from_currency.upper(), 1.0)
    to_rate = r.get(to_currency.upper(), 1.0)
    chf = amount / from_rate
    return chf * to_rate


def calculate_vk(ek: float | None, margin: float) -> float | None:
    """VK = EK / (1 - margin) where margin is 0–1. Returns None if margin >= 1."""
    if ek is None:
        return None
    if margin >= 1.0:
        return None
    return ek / (1.0 - margin)


def actual_margin(ek: float | None, vk: float | None) -> float | None:
    """Return achieved margin (0–1) given EK and VK."""
    if ek is None or vk is None or vk == 0:
        return None
    return (vk - ek) / vk


def margin_color(margin: float | None) -> str:
    """Return a CSS colour string based on margin level."""
    if margin is None:
        return "gray"
    if margin >= MIN_MARGIN_WARNING:
        return "green"
    if margin >= MIN_MARGIN_ERROR:
        return "orange"
    return "red"
