"""Integration tests for product extraction with mocked AI."""

from offerten_converter.application.extract_products import extract_line_items


def _mock_ai_call(user_content: str, system_prompt: str, api_key: str) -> str:
    """Mock AI that returns a fixed JSON response."""
    return """[
        {"sku": "TEST-001", "ean": "1234567890123", "product_name": "Test Product",
         "size": "M", "color": "blue", "category": "Test",
         "unit_price": 49.99, "currency": "EUR",
         "ordered_qty": 5, "min_qty": null, "discount_pct": 10, "notes": null}
    ]"""


class TestExtractProducts:
    def test_extract_with_mocked_ai(self):
        items, usage = extract_line_items(
            "sku  name  price\nTEST-001  Test Product  49.99",
            api_key="sk-test-key",
            call_fn=_mock_ai_call,
        )
        assert len(items) == 1
        assert items[0]["sku"] == "TEST-001"
        assert items[0]["unit_price"] == 49.99
        assert items[0]["ordered_qty"] == 5
        assert usage["input_tokens"] == 0  # mock returns str, no token info

    def test_extract_normalizes_fields(self):
        def mock_partial(content, prompt, key):
            return '[{"sku": "X"}]'

        items, _usage = extract_line_items("data", api_key="sk-test", call_fn=mock_partial)
        assert items[0]["ean"] is None
        assert items[0]["unit_price"] is None
