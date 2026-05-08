"""Tab 1: Konvertieren - Upload -> Extract -> Price -> Export."""

from __future__ import annotations

import logging
import os
import re
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from offerten_converter.application.calculate_prices import enrich_dataframe
from offerten_converter.application.export_quotation import export_to_excel
from offerten_converter.application.extract_products import extract_line_items
from offerten_converter.application.manage_profiles import profile_to_hints
from offerten_converter.application.sanitize_data import sanitize_dataframe
from offerten_converter.infrastructure import extraction_cache
from offerten_converter.infrastructure.ai_extractors import get_call_fn
from offerten_converter.infrastructure.excel_reader import (
    get_recommended_sheet_name,
    get_sheet_names,
    read_offer_file,
)
from offerten_converter.infrastructure.excel_writer import build_excel
from offerten_converter.infrastructure.file_profile_repo import FileProfileRepository
from offerten_converter.ui.state import clear_extraction, get_settings
from offerten_converter.ui.theme import (
    render_field_help,
    render_guidance_panel,
    render_next_steps,
    render_panel_heading,
    render_process_sidebar,
    render_section,
    render_status_card,
    render_system_card,
    render_workflow,
)

logger = logging.getLogger(__name__)

_repo = FileProfileRepository()

_EAN_ALIASES = frozenset([
    "ean", "upc/ean", "upc", "gtin", "barcode", "ean-code", "ean_code",
    "ean nr", "ean-nr", "artikel ean",
])

_PRICE_INPUT_PER_M = 15.0
_PRICE_OUTPUT_PER_M = 75.0
_CHARS_PER_TOKEN = 4
_LOCAL_EXTRACTION_COLUMNS = [
    "sku",
    "ean",
    "product_name",
    "size",
    "color",
    "category",
    "unit_price",
    "currency",
    "ordered_qty",
    "available_qty",
    "availability_status",
    "min_qty",
    "discount_pct",
    "notes",
    "extra_fields",
]


def _read_uploaded_file(uploaded_file):
    """Read an uploaded file while keeping Streamlit concerns in the UI layer."""
    raw_bytes = uploaded_file.getvalue()
    try:
        sheet_names = get_sheet_names(raw_bytes, uploaded_file.name)
        recommended = get_recommended_sheet_name(raw_bytes, uploaded_file.name)
        chosen = recommended or (sheet_names[0] if sheet_names else None)
        if len(sheet_names) > 1:
            index = sheet_names.index(chosen) if chosen in sheet_names else 0
            chosen = st.selectbox(
                "Tabellenblatt auswählen:",
                sheet_names,
                index=index,
                key="sheet_select",
            )

        result = read_offer_file(raw_bytes, uploaded_file.name, chosen)
        if result.was_unpivoted:
            st.success(f"{result.unpivot_info}")

        detected_currency = result.metadata_hints.get("detected_currency")
        if detected_currency:
            st.info(f"Währung erkannt: **{detected_currency}**")
        layout_type = result.metadata_hints.get("layout_type")
        if layout_type:
            st.caption(f"Erkannte Offerten-Struktur: **{layout_type}**")

        return result
    except Exception as exc:
        st.error(f"Fehler beim Lesen der Datei: {exc}")
        st.stop()


def _load_cached_extraction(file_bytes: bytes, result) -> pd.DataFrame | None:
    source_sheet = result.metadata_hints.get("source_sheet")
    keys = [
        extraction_cache.cache_key(file_bytes, source_sheet),
        extraction_cache.file_hash(file_bytes),
    ]
    for key in keys:
        cached = extraction_cache.load(key)
        if cached is not None and not cached.empty:
            return _enforce_import_truth(cached, result.df)
    return None


def _save_cached_extraction(file_bytes: bytes, result, df_extracted: pd.DataFrame) -> None:
    source_sheet = result.metadata_hints.get("source_sheet")
    extraction_cache.save(extraction_cache.cache_key(file_bytes, source_sheet), df_extracted)
    extraction_cache.save(extraction_cache.file_hash(file_bytes), df_extracted)


def _sanitize_prompt_hints(hints: str, blocked_terms: list[str] | None = None) -> str:
    """Sanitize profile/metadata hints before adding them to an AI prompt."""
    if not hints:
        return ""
    df_hints = pd.DataFrame({"hints": [hints]})
    clean_hints, log = sanitize_dataframe(df_hints)
    cleaned = str(clean_hints.iloc[0]["hints"])
    for term in blocked_terms or []:
        term = str(term or "").strip()
        if term:
            cleaned = cleaned.replace(term, "[REDACTED]")
    if log:
        st.caption(f"{len(log)} sensible Angabe(n) aus Profil-/Spalten-Hinweisen entfernt.")
    return cleaned


def _fetch_market_prices_once(extracted_df: pd.DataFrame) -> None:
    if st.session_state.get("market_prices_fetched"):
        return
    st.session_state["market_prices_fetched"] = True

    ean_col = None
    if "ean" in extracted_df.columns:
        ean_col = "ean"
    else:
        for col in extracted_df.columns:
            if col.strip().lower() in _EAN_ALIASES:
                ean_col = col
                break
    if ean_col is None:
        return

    eans = (
        extracted_df[ean_col]
        .dropna()
        .astype(str)
        .str.strip()
        .replace({"nan": "", "None": ""})
    )
    unique_eans = [ean for ean in eans.unique() if ean]
    if not unique_eans:
        return

    try:
        from offerten_converter.infrastructure.market_price_scraper import ToppreiseScraper
    except ImportError:
        return

    scraper = ToppreiseScraper()
    prices: dict[str, float] = {}
    progress = st.progress(0, text="Marktpreise werden geladen ...")
    status = st.empty()

    import time

    for i, ean in enumerate(unique_eans):
        status.caption(f"EAN {ean} ({i + 1}/{len(unique_eans)})")
        price = scraper.fetch_price(ean)
        if price is not None:
            prices[ean] = price
        progress.progress((i + 1) / len(unique_eans))
        if i < len(unique_eans) - 1:
            time.sleep(2.5)

    progress.empty()
    status.empty()
    st.session_state["market_prices"] = prices
    if prices:
        st.success(f"Marktpreise geladen: {len(prices)}/{len(unique_eans)} EANs gefunden.")


def _api_cost_caption(text: str, n_chunks: int) -> None:
    from offerten_converter.application.extract_products import SYSTEM_PROMPT

    system_tokens = len(SYSTEM_PROMPT) // _CHARS_PER_TOKEN
    content_tokens = len(text) // _CHARS_PER_TOKEN
    chunk_tokens = content_tokens // max(n_chunks, 1)
    total_input = (system_tokens + chunk_tokens) * n_chunks
    lines = text.splitlines()
    data_lines = [line for line in lines[1:] if line.strip()]
    sample = data_lines[:20]
    compressed = [re.sub(r" {2,}", " ", line).strip() for line in sample]
    avg_chars = sum(len(line) for line in compressed) / max(len(compressed), 1)
    total_output = int(len(data_lines) * avg_chars * 3.0 / _CHARS_PER_TOKEN)
    cost_usd = (
        total_input / 1_000_000 * _PRICE_INPUT_PER_M
        + total_output / 1_000_000 * _PRICE_OUTPUT_PER_M
    )
    cost_chf = cost_usd * 0.89
    st.caption(f"Geschätzte API-Kosten: ca. **CHF {cost_chf:.3f}**")


def _metadata_hints(result: Any) -> list[str]:
    extra = []
    if result.metadata_hints.get("layout_type"):
        extra.append(f"Detected offer layout: {result.metadata_hints['layout_type']}.")
    if result.metadata_hints.get("column_mapping"):
        extra.append(f"Canonical column mapping: {result.metadata_hints['column_mapping']}.")
    if result.was_unpivoted:
        extra.append(
            "Data was unpivoted: '_size_from_col' = size, "
            "'_qty_from_col' = available_qty. ordered_qty must remain null."
        )
    if result.metadata_hints.get("detected_currency"):
        extra.append(f"Detected currency: {result.metadata_hints['detected_currency']}")
    return extra


def _is_present(value) -> bool:
    return value is not None and not (isinstance(value, float) and pd.isna(value))


def _has_values(series: pd.Series) -> bool:
    values = series.dropna().astype(str).str.strip()
    values = values[~values.str.lower().isin(["", "nan", "none"])]
    return not values.empty


def _enforce_import_truth(df_extracted: pd.DataFrame, import_df: pd.DataFrame) -> pd.DataFrame:
    """Keep structural fields from local import; customers fill ordered_qty later."""
    df = df_extracted.copy().reset_index(drop=True)
    source = import_df.reset_index(drop=True)

    df["ordered_qty"] = None
    if len(source) != len(df):
        return df

    structural_cols = [
        "sku",
        "ean",
        "product_name",
        "size",
        "color",
        "category",
        "available_qty",
        "unit_price",
        "currency",
        "discount_pct",
    ]
    for col in structural_cols:
        if col in source.columns and _has_values(source[col]):
            df[col] = source[col].values
    return df


def _build_local_extraction(result: Any) -> pd.DataFrame | None:
    """Build extracted products from trusted local import columns when possible."""
    source = result.df.copy().reset_index(drop=True)
    if source.empty:
        return None

    has_identity = any(
        col in source.columns and _has_values(source[col])
        for col in ("product_name", "sku", "ean")
    )
    has_price = "unit_price" in source.columns and _has_values(source["unit_price"])
    has_variant_info = any(
        col in source.columns and _has_values(source[col])
        for col in ("size", "color", "available_qty")
    )
    if not (has_identity and has_price and has_variant_info):
        return None

    df = pd.DataFrame(index=source.index)
    for col in _LOCAL_EXTRACTION_COLUMNS:
        if col == "extra_fields":
            df[col] = [{} for _ in range(len(source))]
        elif col in source.columns:
            df[col] = source[col].values
        else:
            df[col] = None

    df["ordered_qty"] = None
    identity_cols = [col for col in ("product_name", "sku", "ean") if col in df.columns]
    if identity_cols:
        identity = df[identity_cols].fillna("").astype(str).agg("".join, axis=1).str.strip()
        df = df[identity != ""]

    return df.reset_index(drop=True) if not df.empty else None


def render():
    settings = get_settings()

    completed_steps: set[int] = set()
    active_step = 1
    has_uploaded_file = (
        st.session_state.get("_file_fingerprint")
        or st.session_state.get("file_uploader") is not None
    )
    if has_uploaded_file:
        completed_steps.add(1)
        active_step = 2
    if st.session_state.get("extracted_df") is not None:
        completed_steps.add(2)
        active_step = 3
    if st.session_state.get("enriched_df") is not None:
        completed_steps.add(3)
        active_step = 4

    render_process_sidebar(active_step)
    render_workflow(active_step, completed_steps)

    form_col, guide_col = st.columns([2.1, 1], gap="large")
    with guide_col:
        render_guidance_panel([
            (
                "Lieferant",
                "Wird lokal für Profil, Export-Dateiname und Zuordnung benötigt.",
                "Missing" if not st.session_state.get("supplier_name", "").strip() else "OK",
                bool(st.session_state.get("supplier_name", "").strip()),
            ),
            (
                "Excel-Datei",
                "Die Offerte mit Artikeln, Varianten, Preisen und Verfügbarkeit.",
                "Missing" if st.session_state.get("file_uploader") is None else "OK",
                st.session_state.get("file_uploader") is not None,
            ),
            (
                "Profil",
                "Optional. Spart Arbeit bei wiederkehrenden Lieferanten.",
                "Optional",
                True,
            ),
        ])
        render_next_steps(active_step)
        render_system_card("Bereit für Import")

    with form_col:
        with st.container(border=True):
            render_panel_heading("Offerte importieren", "upload")
            render_section(
                "Schritt 1",
                "Lieferant & Datei",
                "Lieferant wählen, Excel-Datei importieren und die erkannte Struktur prüfen.",
            )

            col_sup, col_prof = st.columns(2)
            with col_sup:
                supplier_name = st.text_input(
                    "Lieferant *",
                    value=st.session_state["supplier_name"],
                    placeholder="Name des Lieferanten eingeben",
                    help="Pflichtfeld. Wird lokal verwendet und nicht an die API gesendet.",
                )
                render_field_help("Pflicht: Name des Lieferanten. Wird nicht an die API gesendet.")
                st.session_state["supplier_name"] = supplier_name

            with col_prof:
                profiles = _repo.list_profiles()
                if profiles:
                    load_choice = st.selectbox(
                        "Profil laden",
                        ["- kein Profil -"] + profiles,
                        key="profile_load_select",
                        help=(
                            "Optional. Profile merken typische Währungen, Rabatte "
                            "und Spaltenhinweise."
                        ),
                    )
                else:
                    load_choice = "- kein Profil -"
                    st.selectbox("Profil laden", ["- kein Profil -"], disabled=True)
                render_field_help("Optional: spart Arbeit bei wiederkehrenden Lieferanten.")

            loaded_profile = None
            if load_choice != "- kein Profil -":
                loaded_profile = _repo.load(load_choice)
                if loaded_profile and not supplier_name:
                    supplier_name = loaded_profile["name"]
                    st.session_state["supplier_name"] = supplier_name
                if loaded_profile:
                    st.caption(
                        f"Profil: {loaded_profile['name']} | "
                        f"Währung: {loaded_profile.get('typical_currency', '?')} | "
                        f"Rabatt: {loaded_profile.get('typical_discount', 0)}%"
                    )

            uploaded = st.file_uploader(
                "Excel-Datei *",
                type=["xlsx", "xls", "csv"],
                key="file_uploader",
                help="Pflichtfeld. Unterstützt .xlsx, .xls und .csv.",
            )
            render_field_help(
                "Pflicht: Lieferanten-Offerte hochladen. Die Datei wird nur im "
                "Speicher verarbeitet."
            )

    if uploaded is None:
        clear_extraction()
        return

    uploaded_bytes = uploaded.getvalue()
    sheet_key = st.session_state.get("sheet_select", "")
    fingerprint = f"{uploaded.name}::{uploaded.size}::{sheet_key}"
    if st.session_state["_file_fingerprint"] != fingerprint:
        clear_extraction()
        st.session_state["_file_fingerprint"] = fingerprint

    result = _read_uploaded_file(uploaded)
    df_raw = result.df

    file_info = f"{uploaded.name} | {len(df_raw)} Zeilen | {len(df_raw.columns)} Spalten"
    if result.was_unpivoted:
        file_info += f" | {result.unpivot_info}"
    if result.metadata_hints.get("detected_currency"):
        file_info += f" | Währung erkannt: {result.metadata_hints['detected_currency']}"
    render_status_card("Datei erkannt", file_info)

    st.divider()
    render_panel_heading("Produkte erkennen", "scan")
    render_section(
        "Schritt 2",
        "Produkte erkennen",
        "Die Tabelle wird vor jedem API-Call bereinigt. Lieferantennamen und sensible Daten "
        "bleiben aus dem Prompt.",
    )

    df_clean, sanitize_log = sanitize_dataframe(df_raw)
    st.session_state["sanitize_log"] = sanitize_log
    removed = [entry for entry in sanitize_log if entry.startswith("Spalte")]
    if removed:
        render_status_card(
            "Sanitizer aktiv",
            f"{len(removed)} sensible Spalte(n) vor Übermittlung entfernt.",
        )
    else:
        render_status_card(
            "Sanitizer aktiv",
            "Keine sensiblen Spalten erkannt. Die bereinigte Produkttabelle ist bereit.",
        )
    render_status_card(
        "Nächste Entscheidung",
        "Standardmässig nutzt die App Cache oder lokale Erkennung. Die API wird nur verwendet, "
        "wenn Sie die Checkbox bewusst aktivieren.",
    )

    sanitized_text = df_clean.to_string(index=False)

    from offerten_converter.application.extract_products import _split_table_into_chunks

    n_chunks = len(_split_table_into_chunks(sanitized_text))

    col_btn, col_cost = st.columns([2, 3])
    with col_btn:
        extract_btn = st.button(
            "Produkte erkennen",
            type="primary",
            use_container_width=True,
            disabled=not supplier_name.strip(),
        )
    with col_cost:
        st.write("")
        _api_cost_caption(sanitized_text, n_chunks)
    if not supplier_name.strip():
        st.warning(
            "Bitte zuerst den Lieferantennamen ausfüllen. Danach ist die "
            "Produkterkennung aktiv."
        )

    if st.session_state["extracted_df"] is None:
        cached_df = _load_cached_extraction(uploaded_bytes, result)
        if cached_df is not None:
            st.session_state["extracted_df"] = cached_df
            st.session_state["api_usage"] = {"input_tokens": 0, "output_tokens": 0}
            st.success(f"{len(cached_df)} Produkte aus lokalem Cache geladen.")
        else:
            local_df = _build_local_extraction(result)
            if local_df is not None:
                local_df = _enforce_import_truth(local_df, result.df)
                _save_cached_extraction(uploaded_bytes, result, local_df)
                st.session_state["extracted_df"] = local_df
                st.session_state["api_usage"] = {"input_tokens": 0, "output_tokens": 0}
                st.success(f"{len(local_df)} Produkte aus Datei-Struktur ohne API aufgebaut.")

    if st.session_state["extracted_df"] is not None:
        st.caption("Eine Extraktion ist bereits vorhanden. Kein neuer API-Call nötig.")
        force_api = st.checkbox(
            "API-Extraktion erneut ausführen (kostet Tokens)",
            key="force_api_extract",
        )
    else:
        force_api = st.checkbox(
            "API-Extraktion ausführen (kostet Tokens)",
            key="force_api_extract",
        )

    if extract_btn:
        if not force_api:
            if st.session_state["extracted_df"] is not None:
                st.info(
                    "API-Extraktion nicht ausgeführt. "
                    "Die vorhandene lokale Extraktion bleibt aktiv."
                )
            else:
                st.info("API-Extraktion nicht ausgeführt. Bitte zuerst bewusst bestätigen.")
            return
        for key in ("extracted_df", "raw_api_response", "extraction_error", "api_usage"):
            st.session_state[key] = None

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            st.error("ANTHROPIC_API_KEY nicht gesetzt. Bitte in der .env-Datei eintragen.")
            return

        hint_parts = []
        if loaded_profile:
            hint_parts.append(profile_to_hints(loaded_profile))
        hint_parts.extend(_metadata_hints(result))
        blocked_terms = [supplier_name]
        if loaded_profile:
            blocked_terms.append(loaded_profile.get("name", ""))
        hints = _sanitize_prompt_hints(
            " | ".join(part for part in hint_parts if part),
            blocked_terms=blocked_terms,
        )

        with st.spinner("Produkte werden erkannt ..."):
            try:
                items, usage = extract_line_items(
                    sanitized_text,
                    hints,
                    api_key,
                    call_fn=get_call_fn(api_key),
                )
                df_extracted = pd.DataFrame(items)
                df_extracted = _enforce_import_truth(df_extracted, result.df)
                _save_cached_extraction(uploaded_bytes, result, df_extracted)

                st.session_state["extracted_df"] = df_extracted
                st.session_state["api_usage"] = usage
                st.success(f"{len(df_extracted)} Produkte erkannt.")
            except ValueError as exc:
                st.session_state["extraction_error"] = str(exc)
            except RuntimeError as exc:
                st.error(f"Fehler: {exc}")
                return

    if st.session_state.get("extraction_error"):
        st.error("Extraktion fehlgeschlagen - bitte erneut versuchen.")
        return

    if st.session_state["extracted_df"] is None:
        return

    st.session_state["extracted_df"] = _enforce_import_truth(
        st.session_state["extracted_df"],
        result.df,
    )

    _fetch_market_prices_once(st.session_state["extracted_df"])

    st.divider()
    render_panel_heading("Produkte und Preise prüfen", "price")
    render_section(
        "Schritt 3",
        "Produkte & Preise",
        "Mengen, Margen und manuelle Verkaufspreise direkt in der Arbeitstabelle pflegen.",
    )
    render_status_card(
        "Was muss hier geprüft werden?",
        "Pflicht: Menge pro Position. Optional: Marge pro Zeile, manueller VK und Notizen. "
        "Leere manuelle VK-Felder werden automatisch aus EK und Marge berechnet.",
    )

    extracted_df = st.session_state["extracted_df"]
    rates = settings["rates"]
    market_prices = st.session_state.get("market_prices", {})

    ctrl1, ctrl2, ctrl3, ctrl4 = st.columns([1.2, 1, 1.5, 1.5])
    margin_pct = ctrl1.number_input(
        "Standard-Marge %",
        min_value=0.0,
        max_value=99.0,
        value=settings["default_margin"],
        step=0.5,
        format="%.1f",
        key="margin_input",
    )
    target_currency = ctrl2.selectbox(
        "Währung",
        ["CHF", "EUR", "USD"],
        index=["CHF", "EUR", "USD"].index(settings["default_currency"]),
        key="currency_input",
    )
    apply_mp = False
    mp_pct = 0.0
    if market_prices:
        mp_pct = ctrl3.number_input(
            "Marktpreis - %",
            min_value=0.0,
            max_value=99.0,
            value=5.0,
            step=0.5,
            format="%.1f",
            key="mp_pct",
            help="VK aller Produkte auf Marktpreis minus X% setzen",
        )
        ctrl4.write("")
        ctrl4.write("")
        apply_mp = ctrl4.button("Auf alle anwenden", key="apply_mp", use_container_width=True)

    enriched_base = enrich_dataframe(extracted_df, margin_pct, target_currency, rates)

    rows = []
    for _, row in enriched_base.iterrows():
        ean = str(row.get("ean", "") or "").strip()
        mp = market_prices.get(ean) if ean else None
        rows.append({
            "Bezeichnung": row.get("product_name", ""),
            "Grösse": row.get("size", ""),
            "Farbe": row.get("color", ""),
            "Menge": row.get("qty"),
            "EK/Stk": row.get("ek_unit_target"),
            "Marktpreis": mp,
            "Marge %": margin_pct,
            "VK/Stk (manuell)": None,
            "Notizen": str(row.get("notes") or ""),
        })
    unified_df = pd.DataFrame(rows)

    prev = st.session_state.get("_pricing_edits")
    if prev is not None and len(prev) == len(unified_df):
        for col in ("Menge", "Marge %", "VK/Stk (manuell)", "Notizen"):
            if col in prev.columns:
                unified_df[col] = prev[col].values

    if apply_mp:
        for i in range(len(unified_df)):
            mp_val = unified_df.at[i, "Marktpreis"]
            if _is_present(mp_val):
                unified_df.at[i, "VK/Stk (manuell)"] = round(float(mp_val) * (1 - mp_pct / 100), 2)

    has_market = market_prices and any(row["Marktpreis"] is not None for row in rows)

    col_cfg: dict = {
        "Bezeichnung": st.column_config.TextColumn(disabled=True, width="large"),
        "Grösse": st.column_config.TextColumn(disabled=True, width="small"),
        "Farbe": st.column_config.TextColumn(disabled=True, width="small"),
        "Menge": st.column_config.NumberColumn(format="%d", width="small"),
        "EK/Stk": st.column_config.NumberColumn(
            disabled=True,
            format="%.2f",
            label=f"EK/Stk ({target_currency})",
        ),
        "Marktpreis": st.column_config.NumberColumn(
            disabled=True,
            format="%.2f",
            help="Günstigster Preis toppreise.ch - nicht im Export",
        ) if has_market else None,
        "Marge %": st.column_config.NumberColumn(
            min_value=0.0,
            max_value=99.0,
            format="%.1f",
            help="Pro Zeile editierbar",
        ),
        "VK/Stk (manuell)": st.column_config.NumberColumn(
            format="%.2f",
            label=f"VK/Stk ({target_currency})",
            help="Direkt eingeben - überschreibt Marge %. Leer = automatisch.",
        ),
        "Notizen": st.column_config.TextColumn(width="medium"),
    }
    col_cfg = {key: value for key, value in col_cfg.items() if value is not None}

    display_cols = [col for col in unified_df.columns if col in col_cfg or col == "Marktpreis"]
    if not has_market and "Marktpreis" in unified_df.columns:
        display_cols = [col for col in display_cols if col != "Marktpreis"]

    edited = st.data_editor(
        unified_df[display_cols],
        column_config=col_cfg,
        use_container_width=True,
        num_rows="fixed",
        key="unified_editor",
    )
    st.session_state["_pricing_edits"] = edited.copy()
    missing_qty = 0
    if "Menge" in edited.columns:
        missing_qty = int(edited["Menge"].isna().sum())
    if missing_qty:
        st.warning(
            f"{missing_qty} Position(en) haben noch keine Menge. "
            "Bitte Mengen ergänzen oder prüfen, bevor die Offerte exportiert wird."
        )
    else:
        st.success(
            "Alle Positionen haben eine Menge. "
            "Export kann nach der Preisprüfung erstellt werden."
        )

    df_for_export = extracted_df.copy()
    for i, erow in edited.iterrows():
        qty_val = erow.get("Menge")
        if _is_present(qty_val):
            df_for_export.at[i, "ordered_qty"] = qty_val
        note_val = erow.get("Notizen", "")
        if note_val:
            df_for_export.at[i, "notes"] = note_val

    enriched_rows = []
    for i, row in df_for_export.iterrows():
        erow = edited.iloc[i]
        vk_manual = erow.get("VK/Stk (manuell)")
        marge_row = float(erow.get("Marge %") or margin_pct)
        row_df = pd.DataFrame([row])

        try:
            vk_f = float(vk_manual) if vk_manual is not None else None
            if isinstance(vk_manual, float) and pd.isna(vk_manual):
                vk_f = None
        except (ValueError, TypeError):
            vk_f = None

        if vk_f and vk_f > 0:
            row_df["vk_target"] = vk_f
        enriched_row = enrich_dataframe(row_df, marge_row, target_currency, rates)
        enriched_rows.append(enriched_row)

    enriched = pd.concat(enriched_rows, ignore_index=True)
    enriched["market_price"] = enriched["ean"].apply(
        lambda ean: market_prices.get(str(ean).strip()) if ean else None
    )
    st.session_state["enriched_df"] = enriched

    if "_unknown_currency" in enriched.columns:
        unknown = enriched[enriched["_unknown_currency"].fillna(False).astype(bool)]
        if not unknown.empty:
            bad_currencies = unknown["currency"].dropna().unique().tolist()
            st.error(
                f"Unbekannte Währung(en): {', '.join(bad_currencies)} - "
                f"Kein Wechselkurs verfügbar, Umrechnung 1:1 verwendet. "
                f"Bitte Wechselkurs in den Einstellungen nachtragen."
            )

    ek_total = enriched["ek_target"].sum(skipna=True)
    vk_total = enriched["vk_target"].sum(skipna=True)
    avg_marg = enriched["margin_actual"].mean(skipna=True)
    m1, m2, m3 = st.columns(3)
    m1.metric(f"EK Total ({target_currency})", f"{ek_total:,.2f}")
    m2.metric(f"VK Total ({target_currency})", f"{vk_total:,.2f}")
    m3.metric("Ø Marge", f"{avg_marg:.1f}%" if not pd.isna(avg_marg) else "-")

    with st.expander("Erweiterte Optionen"):
        if supplier_name:
            st.markdown("**Lieferantenprofil speichern**")
            pc1, pc2 = st.columns(2)
            prof_currency = pc1.text_input("Typische Währung", value="EUR", key="prof_cur")
            prof_discount = pc2.number_input(
                "Typischer Rabatt %", 0.0, 100.0, 0.0, 0.5, key="prof_disc",
            )
            if st.button("Profil speichern", key="save_profile"):
                _repo.save(supplier_name, prof_currency, prof_discount, "")
                st.success(f"Profil '{supplier_name}' gespeichert.")

    st.divider()
    render_panel_heading("Export erstellen", "export")
    render_section(
        "Schritt 4",
        "Offerte exportieren",
        "Exportbereitschaft prüfen und die standardisierte Reseller-Offerte als Excel laden.",
    )

    effective_supplier = supplier_name or (loaded_profile.get("name", "") if loaded_profile else "")
    created_by = settings.get("company_name", "AMP Sport GmbH")
    valid_days = int(settings.get("valid_days", 30))
    render_guidance_panel([
        (
            "Lieferant",
            "Muss gesetzt sein, damit die Offerte eindeutig benannt werden kann.",
            "Pflicht",
            bool(effective_supplier.strip()),
        ),
        (
            "Positionen",
            "Mindestens eine erkannte Produktposition muss vorhanden sein.",
            "Pflicht",
            not enriched.empty,
        ),
        (
            "Mengen",
            "Mengen sollten vor dem Export kontrolliert sein.",
            "Pflicht",
            missing_qty == 0,
        ),
    ])

    if not effective_supplier:
        st.warning("Bitte zuerst den Lieferantennamen eingeben (Schritt 1).")
    elif enriched.empty:
        st.warning("Keine Positionen vorhanden.")
    else:
        try:
            excel_bytes = export_to_excel(
                enriched,
                effective_supplier,
                created_by,
                target_currency,
                valid_days,
                build_fn=build_excel,
            )
            today_str = date.today().strftime("%Y%m%d")
            filename = f"Offerte_{effective_supplier.replace(' ', '_')}_{today_str}.xlsx"
            st.download_button(
                label=f"Offerte herunterladen ({len(enriched)} Positionen)",
                data=excel_bytes,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True,
            )
        except Exception as exc:
            st.error(f"Export-Fehler: {exc}")
