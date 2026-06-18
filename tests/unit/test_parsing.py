"""Unit tests for the messy-cell number parser (domain/parsing.py)."""

from __future__ import annotations

import math

import pytest

from offerten_converter.domain.parsing import parse_decimal


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # Plain numbers
        ("1077", 1077.0),
        ("89.90", 89.90),
        (35, 35.0),
        (35.5, 35.5),
        # European decimal comma (the Nike-offer regression: prices were dropped)
        ("65,00", 65.0),
        ("129,99", 129.99),
        # Currency symbols and codes glued to the value
        ("65,00 EUR", 65.0),
        ("EUR 89.90", 89.90),
        ("89,90 €", 89.90),
        # Mojibake euro: "65,00 €" exported with a broken encoding -> NBSP + U+FFFD
        ("65,00\xa0�", 65.0),
        ("35,00��", 35.0),
        # Thousands separators (Swiss apostrophe, US comma, EU dot)
        ("1'234.50", 1234.50),
        ("1,234.50", 1234.50),
        ("1.234,50", 1234.50),
        # Trailing "+" availability marker ("500 or more")
        ("500+", 500.0),
        # Blank / non-numeric -> None
        ("", None),
        ("   ", None),
        (None, None),
        ("n/a", None),
        ("WHITE/BLACK", None),
    ],
)
def test_parse_decimal(value, expected):
    result = parse_decimal(value)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)


def test_parse_decimal_rejects_bool_and_nan():
    assert parse_decimal(True) is None
    assert parse_decimal(False) is None
    assert parse_decimal(math.nan) is None
