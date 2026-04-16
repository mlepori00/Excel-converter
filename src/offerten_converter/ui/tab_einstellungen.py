"""Tab 3: Einstellungen – Company name, margins, exchange rates."""

from __future__ import annotations

import streamlit as st

from offerten_converter.ui.state import get_settings


def render():
    """Render the Einstellungen tab."""
    st.header("Einstellungen")
    settings = get_settings()

    st.subheader("Allgemein")
    col_a, col_b = st.columns(2)
    with col_a:
        settings["company_name"] = st.text_input(
            "Firmenname (erscheint im Excel-Header)",
            value=settings["company_name"],
        )
        settings["default_margin"] = st.number_input(
            "Standard-Marge %", 0.0, 99.0, settings["default_margin"], 0.5,
        )
    with col_b:
        settings["default_currency"] = st.selectbox(
            "Standard-Zielwährung",
            ["CHF", "EUR", "USD"],
            index=["CHF", "EUR", "USD"].index(settings["default_currency"]),
        )
        settings["valid_days"] = st.number_input(
            "Gültigkeitsdauer Offerte (Tage)",
            min_value=1, max_value=365, value=int(settings["valid_days"]),
        )

    st.divider()
    st.subheader("Wechselkurse (1 CHF = X Fremdwährung)")

    # Show rate source + refresh button
    rates_source = st.session_state.get("_rates_source", "statisch")
    col_src, col_btn = st.columns([3, 1])
    with col_src:
        if rates_source.startswith("EZB"):
            st.success(f"Kurse geladen von: **{rates_source}**")
        else:
            st.warning(f"Kurse: **{rates_source}** – Standardwerte werden verwendet.")
    with col_btn:
        if st.button("Kurse aktualisieren"):
            st.session_state["_rates_loaded"] = False
            from offerten_converter.ui.state import _try_load_ecb_rates
            _try_load_ecb_rates()
            st.rerun()

    st.caption("Kurse werden automatisch von der Europäischen Zentralbank (EZB) geladen. "
               "Manuelle Anpassungen sind möglich.")

    for currency, rate in sorted(settings["rates"].items()):
        if currency == "CHF":
            continue
        new_rate = st.number_input(
            f"CHF → {currency}", min_value=0.0001,
            value=float(rate), format="%.4f", key=f"rate_{currency}",
        )
        settings["rates"][currency] = new_rate

    st.divider()
    st.subheader("Neue Währung hinzufügen")
    col_nc1, col_nc2, col_nc3 = st.columns([1, 1, 1])
    with col_nc1:
        new_code = st.text_input("ISO-Code (3 Buchstaben)", max_chars=3).upper()
    with col_nc2:
        new_rate_val = st.number_input(
            "Kurs (1 CHF = X)", min_value=0.0001, value=1.0, format="%.4f",
        )
    with col_nc3:
        st.write("")
        st.write("")
        if st.button("Hinzufügen"):
            if len(new_code) == 3 and new_code.isalpha():
                settings["rates"][new_code] = new_rate_val
                st.success(f"Währung {new_code} hinzugefügt.")
                st.rerun()
            else:
                st.error("Bitte gültigen 3-Buchstaben ISO-Code eingeben.")

    st.divider()
    st.subheader("Datenschutz-Info")
    st.info(
        "**Was lokal bleibt:** Hochgeladene Dateien, Lieferantenname, Kundendaten, "
        "Kontaktinformationen, IBAN, UID-Nummern, Lieferantenprofile.\n\n"
        "**Was an Anthropic API gesendet wird:** Nur die bereinigte Produkttabelle "
        "(Artikelbezeichnungen, Preise, Mengen, Kategorien – nach automatischer "
        "Entfernung aller persönlichen Daten).\n\n"
        "**API-Logs:** Anthropic löscht API-Anfragen nach 7 Tagen."
    )
