"""Unit tests for JSON response parsing and repair."""

import pytest

from offerten_converter.application.extract_products import (
    REQUIRED_FIELDS,
    _normalize_item,
    _parse_response,
    _repair_truncated_json,
)


class TestParseResponse:
    def test_valid_json_array(self):
        raw = '[{"sku": "A", "product_name": "Test"}]'
        result = _parse_response(raw)
        assert len(result) == 1
        assert result[0]["sku"] == "A"
        assert result[0]["product_name"] == "Test"
        # Missing fields should be None
        assert result[0]["ean"] is None

    def test_strips_markdown_fences(self):
        raw = '```json\n[{"sku": "B"}]\n```'
        result = _parse_response(raw)
        assert len(result) == 1
        assert result[0]["sku"] == "B"

    def test_non_array_raises(self):
        with pytest.raises(ValueError, match="Expected a JSON array"):
            _parse_response('{"sku": "A"}')

    def test_handles_leading_text(self):
        raw = 'Here are the items: [{"sku": "C"}]'
        result = _parse_response(raw)
        assert result[0]["sku"] == "C"


class TestRepairTruncatedJson:
    def test_repair_incomplete_last_object(self):
        raw = '[{"sku": "A"}, {"sku": "B", "name": "trun'
        repaired = _repair_truncated_json(raw)
        import json
        data = json.loads(repaired)
        assert len(data) == 1
        assert data[0]["sku"] == "A"

    def test_unrecoverable_raises(self):
        with pytest.raises(ValueError):
            _repair_truncated_json("totally broken")


class TestNormalizeItem:
    def test_fills_missing_fields(self):
        result = _normalize_item({"sku": "A"})
        assert set(result.keys()) == set(REQUIRED_FIELDS)
        assert result["sku"] == "A"
        assert result["ean"] is None
        assert result["unit_price"] is None

    def test_ignores_extra_fields(self):
        result = _normalize_item({"sku": "A", "extra_field": "ignored"})
        assert "extra_field" not in result
