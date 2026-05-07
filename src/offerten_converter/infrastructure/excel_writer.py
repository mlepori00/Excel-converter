"""Excel workbook builder – AMP Sport GmbH corporate design."""

from __future__ import annotations

import io
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# ── AMP Sport Corporate Colours ───────────────────────────────────────────────
NAVY        = "1B2D6B"   # dark navy  (logo primary)
CYAN        = "29B5E8"   # light blue (logo accent)
NAVY_LIGHT  = "D6DFF0"   # very light navy – alternating rows
CYAN_LIGHT  = "E8F6FC"   # very light cyan – alternating rows
WHITE       = "FFFFFF"
GREY_BORDER = "B0BEC5"
LIGHT_GREY  = "F5F6FA"   # near-white for label cells

THIN_SIDE   = Side(style="thin", color=GREY_BORDER)
THIN_BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)
NO_BORDER   = Border()

# Path to optional logo (placed at <project_root>/assets/logo.png)
# __file__ = src/offerten_converter/infrastructure/excel_writer.py → 4 levels up = project root
_ASSETS = Path(__file__).resolve().parent.parent.parent.parent / "assets"

OUTPUT_COLUMNS = [
    ("Pos",           "pos"),
    ("Bezeichnung",   "product_name"),
    ("SKU",           "sku"),
    ("EAN",           "ean"),
    ("Grösse",        "size"),
    ("Farbe",         "color"),
    ("Kategorie",     "category"),
    ("Bestellt",      "qty"),
    ("Max. verfügbar","available_qty"),
    ("EK/Stk",        "ek_unit_target"),
    ("EK Total",      "ek_target"),
    ("Marge %",       "margin_actual"),
    ("VK/Stk",        "vk_unit_target"),
    ("VK Total",      "vk_target"),
    ("Währung",       "currency"),
    ("Notizen",       "notes"),
    ("Zusatzinfos",   "extra_fields"),
]

N_COLS = len(OUTPUT_COLUMNS)


# ── Style helpers ─────────────────────────────────────────────────────────────

def _apply(cell, font=None, fill=None, alignment=None, border=THIN_BORDER):
    if font:      cell.font      = font
    if fill:      cell.fill      = fill
    if alignment: cell.alignment = alignment
    if border is not None:
        cell.border = border


def _navy_cell(ws, row, col, value, size=11, bold=True, align="center"):
    c = ws.cell(row=row, column=col, value=value)
    _apply(c,
        font=Font(name="Calibri", size=size, bold=bold, color=WHITE),
        fill=PatternFill("solid", fgColor=NAVY),
        alignment=Alignment(horizontal=align, vertical="center", wrap_text=True),
    )
    return c


def _cyan_cell(ws, row, col, value, size=10, bold=False, align="left"):
    c = ws.cell(row=row, column=col, value=value)
    _apply(c,
        font=Font(name="Calibri", size=size, bold=bold, color=NAVY),
        fill=PatternFill("solid", fgColor=CYAN_LIGHT),
        alignment=Alignment(horizontal=align, vertical="center"),
    )
    return c


def _label_cell(ws, row, col, value, size=9):
    """Light grey label cell (key in key-value meta pairs)."""
    c = ws.cell(row=row, column=col, value=value)
    _apply(c,
        font=Font(name="Calibri", size=size, bold=True, color=NAVY),
        fill=PatternFill("solid", fgColor=LIGHT_GREY),
        alignment=Alignment(horizontal="right", vertical="center"),
    )
    return c


def _value_cell(ws, row, col, value, size=9):
    """Cyan value cell (value in key-value meta pairs)."""
    c = ws.cell(row=row, column=col, value=value)
    _apply(c,
        font=Font(name="Calibri", size=size, bold=False, color=NAVY),
        fill=PatternFill("solid", fgColor=CYAN_LIGHT),
        alignment=Alignment(horizontal="left", vertical="center"),
    )
    return c


def _data_cell(ws, row, col, value, alt=False):
    c = ws.cell(row=row, column=col, value=value)
    _apply(c,
        font=Font(name="Calibri", size=10, color="1A1A2E"),
        fill=PatternFill("solid", fgColor=NAVY_LIGHT if alt else WHITE),
        alignment=Alignment(vertical="center"),
    )
    return c


def _merge(ws, row, c1, c2, value, font, fill, align="left"):
    ws.merge_cells(start_row=row, start_column=c1, end_row=row, end_column=c2)
    c = ws.cell(row=row, column=c1, value=value)
    _apply(c, font=font, fill=fill,
           alignment=Alignment(horizontal=align, vertical="center", wrap_text=True))
    return c


def _cyan_bar(ws, row, height=5):
    ws.row_dimensions[row].height = height
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=N_COLS)
    ws.cell(row=row, column=1).fill = PatternFill("solid", fgColor=CYAN)


# ── Main builder ──────────────────────────────────────────────────────────────

def build_excel(
    df: pd.DataFrame,
    supplier_name: str,
    created_by: str,
    target_currency: str,
    valid_days: int = 30,
) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Offerte"

    today       = date.today()
    valid_until = today + timedelta(days=valid_days)

    # ── Try to embed logo ─────────────────────────────────────────────────────
    logo_path = _ASSETS / "logo.png"
    has_logo = logo_path.exists()

    LOGO_COLS = 2          # columns reserved for logo on the left
    HEADER_START = LOGO_COLS + 1

    # ── Row 1 – company banner ────────────────────────────────────────────────
    ws.row_dimensions[1].height = 50

    if has_logo:
        # Left block: white background to hold logo image
        ws.merge_cells(start_row=1, start_column=1, end_row=2, end_column=LOGO_COLS)
        logo_cell = ws.cell(row=1, column=1)
        logo_cell.fill = PatternFill("solid", fgColor=WHITE)
        logo_cell.border = THIN_BORDER

        try:
            from openpyxl.drawing.image import Image as XlImage
            img = XlImage(str(logo_path))
            # Scale to fit ~2 columns × 2 rows (roughly 110×55 pts)
            img.width  = 110
            img.height = 50
            img.anchor = "A1"
            ws.add_image(img)
        except Exception:
            pass  # logo embedding failed silently – white box stays
    else:
        # No logo: fill logo columns with navy too
        LOGO_COLS = 0
        HEADER_START = 1

    # Right block: "AMP Sport GmbH" title + "OFFERTE" label
    title_end = N_COLS - 2
    _merge(ws, 1, HEADER_START, title_end,
           "AMP Sport GmbH",
           font=Font(name="Calibri", size=20, bold=True, color=WHITE),
           fill=PatternFill("solid", fgColor=NAVY),
           align="left")

    # "OFFERTE" badge on the far right
    ws.merge_cells(start_row=1, start_column=title_end + 1, end_row=1, end_column=N_COLS)
    badge = ws.cell(row=1, column=title_end + 1, value="OFFERTE")
    _apply(badge,
        font=Font(name="Calibri", size=13, bold=True, color=NAVY),
        fill=PatternFill("solid", fgColor=CYAN),
        alignment=Alignment(horizontal="center", vertical="center"),
    )

    # ── Row 2 – address line ──────────────────────────────────────────────────
    ws.row_dimensions[2].height = 16
    if has_logo:
        # Address spans columns 3..N (logo block is merged rows 1-2)
        pass
    addr_start = HEADER_START
    addr_mid   = addr_start + (N_COLS - addr_start) // 2
    _merge(ws, 2, addr_start, addr_mid,
           "Poststrasse 6  |  6302 Zug",
           font=Font(name="Calibri", size=9, color=NAVY),
           fill=PatternFill("solid", fgColor=CYAN_LIGHT),
           align="left")
    _merge(ws, 2, addr_mid + 1, N_COLS,
           "www.ampsport.ch",
           font=Font(name="Calibri", size=9, color=NAVY),
           fill=PatternFill("solid", fgColor=CYAN_LIGHT),
           align="right")

    # ── Row 3 – cyan accent bar ───────────────────────────────────────────────
    _cyan_bar(ws, 3, height=5)

    # ── Rows 4-5 – document meta ──────────────────────────────────────────────
    #  Layout: [Label] [Value] [gap] [Label] [Value]
    #  Split columns into 4 equal chunks: L-label | L-val | R-label | R-val
    q = max(N_COLS // 4, 2)
    meta = [
        (("Lieferant:",    supplier_name),         ("Datum:",      today.strftime("%d.%m.%Y"))),
        (("Erstellt von:", created_by or "AMP Sport GmbH"), ("Gültig bis:", valid_until.strftime("%d.%m.%Y"))),
    ]
    for i, ((ll, lv), (rl, rv)) in enumerate(meta, start=4):
        ws.row_dimensions[i].height = 17

        # Left pair
        ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=q)
        _apply(ws.cell(row=i, column=1, value=ll),
               font=Font(name="Calibri", size=9, bold=True, color=WHITE),
               fill=PatternFill("solid", fgColor=NAVY),
               alignment=Alignment(horizontal="right", vertical="center"))

        ws.merge_cells(start_row=i, start_column=q + 1, end_row=i, end_column=N_COLS // 2)
        _apply(ws.cell(row=i, column=q + 1, value=lv),
               font=Font(name="Calibri", size=9, color=NAVY),
               fill=PatternFill("solid", fgColor=CYAN_LIGHT),
               alignment=Alignment(horizontal="left", vertical="center"))

        # Right pair
        mid = N_COLS // 2
        ws.merge_cells(start_row=i, start_column=mid + 1, end_row=i, end_column=mid + q)
        _apply(ws.cell(row=i, column=mid + 1, value=rl),
               font=Font(name="Calibri", size=9, bold=True, color=WHITE),
               fill=PatternFill("solid", fgColor=NAVY),
               alignment=Alignment(horizontal="right", vertical="center"))

        ws.merge_cells(start_row=i, start_column=mid + q + 1, end_row=i, end_column=N_COLS)
        _apply(ws.cell(row=i, column=mid + q + 1, value=rv),
               font=Font(name="Calibri", size=9, color=NAVY),
               fill=PatternFill("solid", fgColor=CYAN_LIGHT),
               alignment=Alignment(horizontal="left", vertical="center"))

    # ── Row 6 – cyan accent bar ───────────────────────────────────────────────
    _cyan_bar(ws, 6, height=4)

    # ── Row 7 – column headers ────────────────────────────────────────────────
    DATA_START_ROW = 7
    ws.row_dimensions[DATA_START_ROW].height = 22
    for col_idx, (label, _) in enumerate(OUTPUT_COLUMNS, start=1):
        _navy_cell(ws, DATA_START_ROW, col_idx, label, size=10, bold=True)

    # ── Data rows ─────────────────────────────────────────────────────────────
    df_reset = df.reset_index(drop=True)
    data_row = DATA_START_ROW + 1

    for row_idx, (_, series) in enumerate(df_reset.iterrows()):
        alt = row_idx % 2 == 1
        ws.row_dimensions[data_row].height = 16
        for col_idx, (_, field) in enumerate(OUTPUT_COLUMNS, start=1):
            if field == "pos":
                value = row_idx + 1
            elif field == "extra_fields":
                raw = series.get(field)
                value = (
                    " | ".join(f"{k}: {v}" for k, v in raw.items() if v is not None)
                    if isinstance(raw, dict) and raw else None
                )
            else:
                raw = series.get(field)
                if hasattr(raw, "item"):
                    raw = raw.item()
                value = None if (isinstance(raw, float) and pd.isna(raw)) else raw

            cell = _data_cell(ws, data_row, col_idx, value, alt)

            if field in ("ek_unit_target", "ek_target", "vk_unit_target", "vk_target"):
                cell.number_format = f'#,##0.00\\ "{target_currency}"'
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif field == "margin_actual":
                cell.number_format = '0.00"%"'
                cell.alignment = Alignment(horizontal="right", vertical="center")
                try:
                    v = float(value)
                    fg = "27AE60" if v >= 20 else ("E67E22" if v >= 10 else "E74C3C")
                    cell.font = Font(name="Calibri", size=10, bold=True, color=fg)
                except (TypeError, ValueError):
                    pass
            elif field in ("qty", "available_qty"):
                cell.number_format = "0"
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif field in ("pos", "sku", "ean"):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif field == "product_name":
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=False)

        data_row += 1

    # ── Total row ─────────────────────────────────────────────────────────────
    total_row = data_row
    ws.row_dimensions[total_row].height = 20
    col_map = {field: idx + 1 for idx, (_, field) in enumerate(OUTPUT_COLUMNS)}

    for col_idx in range(1, N_COLS + 1):
        c = ws.cell(row=total_row, column=col_idx)
        c.fill   = PatternFill("solid", fgColor=NAVY)
        c.font   = Font(name="Calibri", size=10, bold=True, color=WHITE)
        c.border = THIN_BORDER
        c.alignment = Alignment(vertical="center")

    ws.cell(row=total_row, column=1).value = "TOTAL"
    ws.cell(row=total_row, column=1).alignment = Alignment(
        horizontal="center", vertical="center"
    )

    ek_start = DATA_START_ROW + 1
    ek_end   = data_row - 1

    if len(df_reset) > 0:
        qty_letter = get_column_letter(col_map["qty"])
        ek_letter  = get_column_letter(col_map["ek_target"])
        vk_letter  = get_column_letter(col_map["vk_target"])

        qty_c = ws.cell(row=total_row, column=col_map["qty"])
        qty_c.value         = f"=SUM({qty_letter}{ek_start}:{qty_letter}{ek_end})"
        qty_c.number_format = "0"
        qty_c.alignment     = Alignment(horizontal="center", vertical="center")

        if "available_qty" in col_map:
            avail_letter = get_column_letter(col_map["available_qty"])
            avail_c = ws.cell(row=total_row, column=col_map["available_qty"])
            avail_c.value         = f"=SUM({avail_letter}{ek_start}:{avail_letter}{ek_end})"
            avail_c.number_format = "0"
            avail_c.alignment     = Alignment(horizontal="center", vertical="center")

        ek_c = ws.cell(row=total_row, column=col_map["ek_target"])
        ek_c.value         = f"=SUM({ek_letter}{ek_start}:{ek_letter}{ek_end})"
        ek_c.number_format = f'#,##0.00\\ "{target_currency}"'
        ek_c.alignment     = Alignment(horizontal="right", vertical="center")

        vk_c = ws.cell(row=total_row, column=col_map["vk_target"])
        vk_c.value         = f"=SUM({vk_letter}{ek_start}:{vk_letter}{ek_end})"
        vk_c.number_format = f'#,##0.00\\ "{target_currency}"'
        vk_c.alignment     = Alignment(horizontal="right", vertical="center")

    # ── Freeze, autofilter, column widths ─────────────────────────────────────
    ws.freeze_panes = ws.cell(row=DATA_START_ROW + 1, column=1)
    ws.auto_filter.ref = (
        f"A{DATA_START_ROW}:{get_column_letter(N_COLS)}{data_row - 1}"
    )

    col_widths = {
        "pos": 5, "product_name": 38, "sku": 14, "ean": 16,
        "size": 8, "color": 13, "category": 14, "qty": 9, "available_qty": 14,
        "ek_unit_target": 12, "ek_target": 13, "margin_actual": 10,
        "vk_unit_target": 12, "vk_target": 13,
        "currency": 9, "notes": 22, "extra_fields": 32,
    }
    for col_idx, (_, field) in enumerate(OUTPUT_COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = col_widths.get(field, 12)

    # ── Footer ────────────────────────────────────────────────────────────────
    footer_row = total_row + 2
    ws.row_dimensions[footer_row].height = 14
    ws.merge_cells(
        start_row=footer_row, start_column=1,
        end_row=footer_row,   end_column=N_COLS,
    )
    c = ws.cell(
        row=footer_row, column=1,
        value="AMP Sport GmbH  ·  Poststrasse 6, 6302 Zug  ·  www.ampsport.ch",
    )
    c.font      = Font(name="Calibri", size=8, italic=True, color="7F8C8D")
    c.alignment = Alignment(horizontal="center", vertical="center")
    c.border    = NO_BORDER

    # Thin top border on footer to separate from total
    ws.row_dimensions[total_row + 1].height = 4

    # ── Page setup ────────────────────────────────────────────────────────────
    ws.page_setup.orientation    = "landscape"
    ws.page_setup.fitToPage      = True
    ws.page_setup.fitToWidth     = 1
    ws.page_setup.fitToHeight    = 0
    ws.print_title_rows          = f"1:{DATA_START_ROW}"  # repeat header on each page

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()
