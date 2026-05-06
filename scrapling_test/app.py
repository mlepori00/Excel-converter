"""
Scrapling Test – EAN Preisabgleich
Starten: streamlit run scrapling_test/app.py
"""
import io, sys, os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import streamlit as st
from scraper import (
    scrape_toppreise_by_ean, scrape_toppreise_by_name,
    scrape_toppreise, scrape_galaxus
)

st.set_page_config(page_title="EAN Preisabgleich – Test", page_icon="🔍", layout="wide")
st.title("🔍 EAN Preisabgleich – Scrapling Test")
st.caption("Kein Claude API, keine Kosten.")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Einstellungen")
    max_eans = st.number_input("Max. EANs (Excel)", min_value=1, max_value=50, value=5)
    ean_column  = st.text_input("EAN-Spalte", value="EAN")
    name_column = st.text_input("Name-Spalte", value="Bezeichnung")
    st.divider()
    st.markdown("**Logik:** EAN vorhanden → präzise Suche. Keine EAN → Suche mit Produktname.")

# ── Tab-Layout ────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["🔢 EAN-Suche", "🔤 Name-Suche", "📊 Excel-Vergleich"])


def _show_result(r):
    badge = "🎯 EAN" if r.query_type == "ean" else "〜 Name (ungefähr)"
    if r.status == "found":
        st.success(f"✅ Gefunden via {r.source}  |  {badge}")
        c = st.columns(4)
        c[0].metric("Gefundenes Produkt", r.product_name or "–")
        c[1].metric("Preis ex. Versand", f"{r.currency} {r.price:.2f}" if r.price else "–")
        c[2].metric("Preis inkl. Versand", f"{r.currency} {r.price_incl_ship:.2f}" if r.price_incl_ship else "–")
        c[3].metric("Angebote", r.num_offers or "–")
        if r.product_url:
            st.markdown(f"[🔗 Auf toppreise.ch ansehen]({r.product_url})")
    elif r.status == "not_found":
        st.warning(f"⚠️ Nicht gefunden auf {r.source}  |  {badge}")
    else:
        st.error(f"❌ Fehler – {r.source}")
        st.code(r.error_message or "(kein Text)")


# ── Tab 1: EAN-Suche ──────────────────────────────────────────────────────────
with tab1:
    st.subheader("Suche mit EAN-Nummer")
    st.caption("Präzise – findet genau dieses Produkt")
    col1, col2 = st.columns([3, 1])
    with col1:
        ean_input = st.text_input("EAN:", placeholder="z.B. 190665668964", key="ean_input")
    with col2:
        st.write("")
        st.write("")
        run_ean = st.button("Suchen", type="primary", key="run_ean")

    if run_ean and ean_input.strip():
        try:
            with st.spinner("Suche auf toppreise.ch..."):
                r = scrape_toppreise_by_ean(ean_input.strip())
            _show_result(r)
        except Exception:
            import traceback
            st.error("Fehler:"); st.code(traceback.format_exc())


# ── Tab 2: Name-Suche ─────────────────────────────────────────────────────────
with tab2:
    st.subheader("Suche mit Produktname")
    st.caption("Ungefähr – nützlich wenn keine EAN vorhanden. Prüfe ob das gefundene Produkt stimmt.")

    col1, col2 = st.columns([3, 1])
    with col1:
        name_input = st.text_input(
            "Produktname:",
            placeholder="z.B. Helly Hansen Arctic Ocean Jacket Men L",
            key="name_input"
        )
    with col2:
        st.write("")
        st.write("")
        run_name = st.button("Suchen", type="primary", key="run_name")

    if run_name and name_input.strip():
        try:
            with st.spinner("Suche auf toppreise.ch..."):
                r = scrape_toppreise_by_name(name_input.strip())
            _show_result(r)

            if r.status == "found":
                st.info(
                    "⚠️ **Namenssuche ist unschärfer als EAN-Suche.** "
                    "Prüfe ob das gefundene Produkt wirklich dem gesuchten entspricht."
                )
        except Exception:
            import traceback
            st.error("Fehler:"); st.code(traceback.format_exc())


# ── Tab 3: Excel-Vergleich ────────────────────────────────────────────────────
with tab3:
    st.subheader("Excel mit EAN und/oder Produktname")
    st.caption(
        "Für jede Zeile: EAN vorhanden → EAN-Suche (🎯). "
        "Keine EAN → Name-Suche (〜). Beides parallel testbar."
    )

    uploaded = st.file_uploader("Excel hochladen (.xlsx)", type=["xlsx"])

    if uploaded:
        try:
            df = pd.read_excel(uploaded)
            st.write(f"Spalten: `{list(df.columns)}`")

            # Auto-detect EAN column
            EAN_ALIASES = ["ean", "upc/ean", "upc", "gtin", "barcode",
                           "ean-code", "ean_code", "ean nr", "ean-nr", "artikel ean"]
            detected_ean_col = None
            for col in df.columns:
                if col.strip().lower() in EAN_ALIASES:
                    detected_ean_col = col
                    break

            if detected_ean_col:
                if detected_ean_col != ean_column:
                    st.success(f"EAN-Spalte automatisch erkannt: **{detected_ean_col}**")
                active_ean_col = detected_ean_col
            elif ean_column in df.columns:
                active_ean_col = ean_column
            else:
                active_ean_col = None
                st.error(
                    f"Keine EAN-Spalte gefunden. "
                    f"Bekannte Namen: {', '.join(EAN_ALIASES)}. "
                    f"Oder manuell in der Sidebar setzen."
                )

            if active_ean_col:
                rows_to_scrape = df.head(max_eans)

                # Vorschau: EAN-Spalte + Anzahl leere Zellen
                eans_preview = rows_to_scrape[active_ean_col].astype(str).str.strip()
                n_with_ean    = eans_preview[~eans_preview.isin(["", "nan", "None"])].count()
                n_without_ean = len(rows_to_scrape) - n_with_ean

                st.dataframe(rows_to_scrape[[active_ean_col]].head(max_eans), use_container_width=True)
                col_a, col_b = st.columns(2)
                col_a.metric("✅ Mit EAN", n_with_ean)
                col_b.metric("⚪ Ohne EAN (werden übersprungen)", n_without_ean)

                if st.button("🚀 Starten", type="primary"):
                    progress = st.progress(0)
                    status_txt = st.empty()
                    results = []

                    for i, (_, row) in enumerate(rows_to_scrape.iterrows()):
                        ean = str(row.get(active_ean_col, "")).strip()
                        ean = "" if ean in ("nan", "None") else ean

                        progress.progress(i / len(rows_to_scrape))

                        if not ean:
                            status_txt.text(f"{i+1}/{len(rows_to_scrape)}: Keine EAN – übersprungen")
                            results.append({
                                "EAN": "–",
                                "Status": "⚪ Keine EAN",
                                "Gefundenes Produkt": "–",
                                "Preis ex. Versand (CHF)": None,
                                "Preis inkl. Versand (CHF)": None,
                                "Angebote": None,
                                "URL": "–",
                            })
                            continue

                        status_txt.text(f"{i+1}/{len(rows_to_scrape)}: Suche EAN {ean}")
                        r = scrape_toppreise(ean=ean, name=None)
                        results.append({
                            "EAN": ean,
                            "Status": {"found": "✅", "not_found": "⚠️", "error": "❌"}.get(r.status),
                            "Gefundenes Produkt": r.product_name or "–",
                            "Preis ex. Versand (CHF)": r.price,
                            "Preis inkl. Versand (CHF)": r.price_incl_ship,
                            "Angebote": r.num_offers,
                            "URL": r.product_url or "–",
                        })

                        if i < len(rows_to_scrape) - 1:
                            import time; time.sleep(2.5)

                    progress.progress(1.0)
                    status_txt.text("Fertig!")

                    result_df = pd.DataFrame(results)

                    found = sum(1 for r in results if r["Status"] == "✅")
                    not_found = sum(1 for r in results if r["Status"] == "⚠️")
                    errors = sum(1 for r in results if r["Status"] == "❌")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("✅ Gefunden", found)
                    c2.metric("⚠️ Nicht gefunden", not_found)
                    c3.metric("❌ Fehler", errors)

                    st.dataframe(result_df, use_container_width=True)

                    buf = io.BytesIO()
                    result_df.to_excel(buf, index=False)
                    st.download_button(
                        "📥 Resultate herunterladen",
                        data=buf.getvalue(),
                        file_name="preisabgleich_resultat.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

        except Exception:
            import traceback
            st.error("Fehler:"); st.code(traceback.format_exc())

st.divider()
st.caption("Scrapling Test Branch – kein Produktionscode, keine API-Kosten")
