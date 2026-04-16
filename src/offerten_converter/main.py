"""Offerten Converter – Streamlit entry point.

Run with:  streamlit run src/offerten_converter/main.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure the src/ directory is on the Python path so that
# `offerten_converter` is importable regardless of how Streamlit is launched.
_SRC_DIR = str(Path(__file__).resolve().parent.parent)
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import streamlit as st
from dotenv import load_dotenv

from offerten_converter.ui import tab_einstellungen, tab_konvertieren, tab_lieferanten
from offerten_converter.ui.state import init_state

# Bootstrap – search for .env starting from the project root (two levels up from this file)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=True)
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")

st.set_page_config(
    page_title="Offerten Converter",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_state()


def main():
    st.title("Offerten Converter")
    st.caption("Lieferanten-Offerte → KI-Extraktion → Preiskalkulation → Reseller-Export")

    tab1, tab2, tab3 = st.tabs(["Konvertieren", "Lieferanten", "Einstellungen"])

    with tab1:
        tab_konvertieren.render()
    with tab2:
        tab_lieferanten.render()
    with tab3:
        tab_einstellungen.render()


if __name__ == "__main__":
    main()
