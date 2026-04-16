"""Unit tests for domain pricing functions."""

import pytest

from offerten_converter.domain.pricing import (
    actual_margin,
    calculate_vk,
    convert_to_target,
    margin_color,
)


class TestConvertToTarget:
    def test_eur_to_chf(self):
        result = convert_to_target(10.0, "EUR", "CHF")
        assert result == pytest.approx(10.0 / 0.955, rel=1e-4)

    def test_same_currency(self):
        assert convert_to_target(100.0, "CHF", "CHF") == pytest.approx(100.0)

    def test_none_input(self):
        assert convert_to_target(None, "EUR", "CHF") is None

    def test_usd_to_eur(self):
        result = convert_to_target(10.0, "USD", "EUR")
        chf = 10.0 / 1.09
        expected = chf * 0.955
        assert result == pytest.approx(expected, rel=1e-4)

    def test_custom_rates(self):
        rates = {"CHF": 1.0, "EUR": 1.0, "USD": 2.0}
        result = convert_to_target(10.0, "USD", "EUR")  # default rates
        custom = convert_to_target(10.0, "USD", "EUR", rates)
        assert custom == pytest.approx(5.0)  # 10/2 * 1
        assert result != custom

    def test_case_insensitive(self):
        a = convert_to_target(10.0, "eur", "chf")
        b = convert_to_target(10.0, "EUR", "CHF")
        assert a == pytest.approx(b)


class TestCalculateVk:
    def test_normal(self):
        assert calculate_vk(60.0, 0.4) == pytest.approx(100.0)

    def test_none_ek(self):
        assert calculate_vk(None, 0.4) is None

    def test_margin_100_returns_none(self):
        assert calculate_vk(60.0, 1.0) is None

    def test_margin_over_100_returns_none(self):
        assert calculate_vk(60.0, 1.5) is None

    def test_zero_margin(self):
        assert calculate_vk(60.0, 0.0) == pytest.approx(60.0)


class TestActualMargin:
    def test_normal(self):
        assert actual_margin(60.0, 100.0) == pytest.approx(0.4)

    def test_none_ek(self):
        assert actual_margin(None, 100.0) is None

    def test_none_vk(self):
        assert actual_margin(60.0, None) is None

    def test_zero_vk(self):
        assert actual_margin(60.0, 0.0) is None


class TestMarginColor:
    def test_green_above_20(self):
        assert margin_color(0.40) == "green"
        assert margin_color(0.20) == "green"

    def test_orange_between_10_and_20(self):
        assert margin_color(0.15) == "orange"
        assert margin_color(0.10) == "orange"

    def test_red_below_10(self):
        assert margin_color(0.05) == "red"
        assert margin_color(0.0) == "red"

    def test_none_is_gray(self):
        assert margin_color(None) == "gray"
