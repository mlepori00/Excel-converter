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

    def test_multichunk_preserves_order_and_sums_tokens(self):
        """Concurrent chunk extraction must keep source order and total tokens."""
        import re

        header = "sku  name  price"
        rows = "\n".join(f"S{i:04d}  Item{i}  9.99" for i in range(400))
        text = header + "\n" + rows

        parts_seen = []

        def mock(content, prompt, key):
            m = re.search(r"\[Part (\d+) of (\d+)\]", content)
            part = int(m.group(1)) if m else 1
            parts_seen.append(part)
            # One item per chunk, tagged with the chunk's part number.
            return (f'[{{"sku": "PART-{part:03d}", "currency": "EUR"}}]', 10, 20)

        items, usage = extract_line_items(text, api_key="sk-test", call_fn=mock)

        assert len(parts_seen) > 1  # actually split into multiple chunks
        skus = [it["sku"] for it in items]
        assert skus == sorted(skus)  # reassembled in original chunk order
        assert usage["input_tokens"] == 10 * len(parts_seen)
        assert usage["output_tokens"] == 20 * len(parts_seen)
