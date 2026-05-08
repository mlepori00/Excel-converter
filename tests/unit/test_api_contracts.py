"""Tests for the frontend rebuild API contracts."""

from __future__ import annotations

import math

import pandas as pd

from offerten_converter.api.mappers import (
    build_export_preview,
    build_prepare_state,
    build_workflow_steps,
    dataframe_to_product_rows,
    pricing_summary_from_enriched_df,
)
from offerten_converter.api.schemas import RequirementStatus, WorkflowStep, to_jsonable


def test_prepare_state_marks_required_fields() -> None:
    state = build_prepare_state(
        supplier_name="",
        selected_profile=None,
        file_metadata=None,
    )

    assert state.can_continue is False
    assert [item.status for item in state.requirements] == [
        RequirementStatus.MISSING,
        RequirementStatus.MISSING,
        RequirementStatus.OPTIONAL,
    ]


def test_workflow_steps_encode_active_and_completed_state() -> None:
    steps = build_workflow_steps(
        WorkflowStep.REVIEW_PRICES,
        completed_steps={WorkflowStep.PREPARE_FILE, WorkflowStep.RECOGNIZE_PRODUCTS},
    )

    assert steps[0].completed is True
    assert steps[1].completed is True
    assert steps[2].active is True
    assert steps[3].active is False


def test_product_rows_are_json_safe_and_mark_missing_qty() -> None:
    df = pd.DataFrame([
        {
            "sku": "A-1",
            "ean": float("nan"),
            "product_name": "Nike Shoe",
            "unit_price": "129.99",
            "currency": "EUR",
            "ordered_qty": None,
            "available_qty": "7",
            "discount_pct": "",
        }
    ])

    rows = dataframe_to_product_rows(df)

    assert rows[0].ean is None
    assert rows[0].unit_price == 129.99
    assert rows[0].available_qty == 7
    assert rows[0].discount_pct is None
    assert rows[0].status == RequirementStatus.MISSING
    assert to_jsonable(rows[0])["status"] == "missing"


def test_pricing_summary_blocks_continue_when_prices_are_missing() -> None:
    enriched = pd.DataFrame([
        {
            "qty": 2,
            "ek_unit_target": 50.0,
            "ek_target": 100.0,
            "vk_target": 160.0,
            "margin_actual": 37.5,
            "_unknown_currency": False,
        },
        {
            "qty": 1,
            "ek_unit_target": math.nan,
            "ek_target": math.nan,
            "vk_target": math.nan,
            "margin_actual": math.nan,
            "_unknown_currency": False,
        },
    ])

    summary = pricing_summary_from_enriched_df(enriched, "CHF")

    assert summary.product_count == 2
    assert summary.missing_qty_count == 0
    assert summary.missing_price_count == 1
    assert summary.can_continue is False


def test_export_preview_requires_supplier_positions_quantities_and_prices() -> None:
    preview = build_export_preview(
        supplier_name="Nike",
        created_by="AMP Sport",
        target_currency="CHF",
        valid_days=30,
        product_count=27,
        missing_qty_count=0,
        missing_price_count=0,
    )

    assert preview.can_download is True
    assert preview.filename.startswith("Offerte_Nike_")
    assert all(item.status == RequirementStatus.OK for item in preview.requirements)

