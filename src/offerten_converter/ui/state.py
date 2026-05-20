"""Session state helpers for the Streamlit UI."""

from __future__ import annotations

import streamlit as st

from offerten_converter.domain.pricing import DEFAULT_RATES


def init_state():
    """Initialize session state with defaults."""
    defaults = {
        "extracted_df": None,
        "enriched_df": None,
        "supplier_name": "",
        "sanitize_log": [],
        "raw_api_response": None,
        "extraction_error": None,
        "_file_fingerprint": None,
        "_rates_source": "statisch",   # "EZB (YYYY-MM-DD)" or "statisch"
        "_rates_loaded": False,
        "market_prices": {},           # {ean: price_chf}
        "market_prices_fetched": False,
        "column_mapping": None,        # {original_col: canonical_field} from Claude
        "column_mapping_done": False,
        "column_mapping_skipped": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def clear_extraction():
    """Reset all extraction results."""
    st.session_state["extracted_df"] = None
    st.session_state["enriched_df"] = None
    st.session_state["sanitize_log"] = []
    st.session_state["raw_api_response"] = None
    st.session_state["extraction_error"] = None
    st.session_state["market_prices"] = {}
    st.session_state["market_prices_fetched"] = False
    st.session_state["force_api_extract"] = False
    st.session_state["column_mapping"] = None
    st.session_state["column_mapping_done"] = False
    st.session_state["column_mapping_skipped"] = False


def get_settings() -> dict:
    """Get or initialize persisted settings."""
    if "settings" not in st.session_state:
        st.session_state["settings"] = {
            "default_margin": 40.0,
            "default_currency": "CHF",
            "company_name": "Meine Firma AG",
            "valid_days": 30,
            "rates": dict(DEFAULT_RATES),
        }

    # Load live ECB rates once per session (on first call)
    if not st.session_state.get("_rates_loaded"):
        _try_load_ecb_rates()

    return st.session_state["settings"]


def _try_load_ecb_rates() -> None:
    """Fetch live rates from ECB and update settings. Silently falls back to static."""
    from offerten_converter.infrastructure.ecb_rates import fetch_ecb_rates

    st.session_state["_rates_loaded"] = True  # mark attempted regardless of outcome
    result = fetch_ecb_rates()

    if result is None:
        st.session_state["_rates_source"] = "statisch (EZB nicht erreichbar)"
        return

    live_rates, date_str = result

    # Merge live rates into existing rates dict – keep any custom currencies the user added
    settings = st.session_state["settings"]
    for currency, rate in live_rates.items():
        settings["rates"][currency] = rate

    st.session_state["_rates_source"] = f"EZB ({date_str})"
