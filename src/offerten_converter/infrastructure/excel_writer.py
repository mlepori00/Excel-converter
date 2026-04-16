"""Excel workbook builder – creates formatted reseller quotation with openpyxl."""

from __future__ import annotations

import io
from datetime import date, timedelta

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HEADER_BG = "1B3A6B"
HEADER_FG = "FFFFFF"
ROW_ALT_BG = "EBF4FB"
ROW_STD_BG = "FFFFFF"

THIN_SIDE = Side(style="thin", color="C0C0C0")
THIN_BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)

OUTPUT_COLUMNS = [
    ("Pos", "pos"),
    ("Bezeichnung", "product_name"),
    ("SKU", "sku"),
    ("EAN", "ean"),
    ("Grösse", "size"),
    ("Farbe", "color"),
    ("Kategorie", "category"),
    ("Menge", "qty"),
    ("EK/Stk", "ek_unit_target"),
    ("EK Total", "ek_target"),
    ("Marge %", "margin_actual"),
    ("VK/Stk", "vk_unit_target"),
    ("VK Total", "vk_target"),
    ("Währung", "currency"),
    ("Notizen", "notes"),
    ("Zusatzinfos", "extra_fields"),  # catch-all for unmapped supplier columns
]


def _header_cell(ws, row: int, col: int, value: str):
    cell = ws.cell(row=row, column=col, value=value)
    cell.font = Font(name="Calibri", size=11, bold=True, color=HEADER_FG)
    cell.fill = PatternFill("solid", fgColor=HEADER_BG)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = THIN_BORDER
    return cell


def _data_cell(ws, row: int, col: int, value, alt: bool = False):
    cell = ws.cell(row=row, column=col, value=value)
    cell.font = Font(name="Calibri", size=10)
    cell.fill = PatternFill("solid", fgColor=ROW_ALT_BG if alt else ROW_STD_BG)
    cell.alignment = Alignment(vertical="center")
    cell.border = THIN_BORDER
    return cell


def build_excel(
    df: pd.DataFrame,
    supplier_name: str,
    created_by: str,
    target_currency: str,
    valid_days: int = 30,
) -> bytes:
    """Build and return the Excel file as raw bytes (never touches disk)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Offerte"

    today = date.today()
    valid_until = today + timedelta(days=valid_days)

    # Header info block (rows 1-4)
    meta = [
        ("Lieferant", supplier_name),
        ("Datum", today.strftime("%d.%m.%Y")),
        ("Erstellt von", created_by),
        ("Gültig bis", valid_until.strftime("%d.%m.%Y")),
    ]
    for i, (label, value) in enumerate(meta, start=1):
        lbl_cell = ws.cell(row=i, column=1, value=label)
        lbl_cell.font = Font(name="Calibri", size=10, bold=True)
        lbl_cell.fill = PatternFill("solid", fgColor="D6E4F0")
        val_cell = ws.cell(row=i, column=2, value=value)
        val_cell.font = Font(name="Calibri", size=10)

    DATA_START_ROW = 6

    # Column header row
    for col_idx, (label, _) in enumerate(OUTPUT_COLUMNS, start=1):
        _header_cell(ws, DATA_START_ROW, col_idx, label)

    # Data rows
    df_reset = df.reset_index(drop=True)
    data_row = DATA_START_ROW + 1

    for row_idx, (_, series) in enumerate(df_reset.iterrows()):
        alt = row_idx % 2 == 1
        for col_idx, (_, field) in enumerate(OUTPUT_COLUMNS, start=1):
            if field == "pos":
                value = row_idx + 1
            elif field == "extra_fields":
                # Serialize dict → "KEY: val | KEY2: val2"
                raw = series.get(field)
                if isinstance(raw, dict) and raw:
                    value = " | ".join(
                        f"{k}: {v}" for k, v in raw.items() if v is not None
                    )
                else:
                    value = None
            else:
                raw = series.get(field)
                if hasattr(raw, "item"):
                    raw = raw.item()
                value = None if pd.isna(raw) else raw

            cell = _data_cell(ws, data_row, col_idx, value, alt)

            if field in ("ek_unit_target", "ek_target", "vk_unit_target", "vk_target"):
                cell.number_format = f'#,##0.00\\ "{target_currency}"'
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif field == "margin_actual":
                cell.number_format = '0.00"%"'
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif field == "qty":
                cell.number_format = "0"
                cell.alignment = Alignment(horizontal="center", vertical="center")

        data_row += 1

    # Footer / TOTAL row
    total_row = data_row
    n_data = len(df_reset)
    col_count = len(OUTPUT_COLUMNS)

    col_map = {field: idx + 1 for idx, (_, field) in enumerate(OUTPUT_COLUMNS)}
    ek_col = get_column_letter(col_map["ek_target"])
    vk_col = get_column_letter(col_map["vk_target"])

    for col_idx in range(1, col_count + 1):
        cell = ws.cell(row=total_row, column=col_idx)
        cell.font = Font(name="Calibri", size=10, bold=True)
        cell.fill = PatternFill("solid", fgColor="D6E4F0")
        cell.border = THIN_BORDER

    ws.cell(row=total_row, column=1).value = "TOTAL"

    ek_start = DATA_START_ROW + 1
    ek_end = data_row - 1

    if n_data > 0:
        # Quantity total
        qty_col_letter = get_column_letter(col_map["qty"])
        qty_cell = ws.cell(row=total_row, column=col_map["qty"])
        qty_cell.value = f"=SUM({qty_col_letter}{ek_start}:{qty_col_letter}{ek_end})"
        qty_cell.number_format = "0"
        qty_cell.alignment = Alignment(horizontal="center", vertical="center")

        # EK Total sum
        ek_cell = ws.cell(row=total_row, column=col_map["ek_target"])
        ek_cell.value = f"=SUM({ek_col}{ek_start}:{ek_col}{ek_end})"
        ek_cell.number_format = f'#,##0.00\\ "{target_currency}"'
        ek_cell.alignment = Alignment(horizontal="right", vertical="center")

        # VK Total sum
        vk_cell = ws.cell(row=total_row, column=col_map["vk_target"])
        vk_cell.value = f"=SUM({vk_col}{ek_start}:{vk_col}{ek_end})"
        vk_cell.number_format = f'#,##0.00\\ "{target_currency}"'
        vk_cell.alignment = Alignment(horizontal="right", vertical="center")

    # Freeze pane, autofilter, column widths
    ws.freeze_panes = ws.cell(row=DATA_START_ROW + 1, column=1)
    ws.auto_filter.ref = f"A{DATA_START_ROW}:{get_column_letter(col_count)}{data_row - 1}"

    for col_idx, (label, field) in enumerate(OUTPUT_COLUMNS, start=1):
        col_letter = get_column_letter(col_idx)
        max_len = len(label)
        for row_i in range(DATA_START_ROW + 1, min(data_row, DATA_START_ROW + 201)):
            val = ws.cell(row=row_i, column=col_idx).value
            if val is not None:
                max_len = max(max_len, len(str(val)))
        ws.column_dimensions[col_letter].width = min(max_len + 4, 40)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()
