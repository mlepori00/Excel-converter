"""Tab 2: Lieferanten – Manage saved supplier profiles."""

from __future__ import annotations

import streamlit as st

from offerten_converter.infrastructure.file_profile_repo import FileProfileRepository

_repo = FileProfileRepository()


def render():
    """Render the Lieferanten tab."""
    st.header("Lieferantenprofile verwalten")

    profiles = _repo.list_profiles()
    if not profiles:
        st.info(
            "Noch keine Profile vorhanden. "
            "Erstelle ein Profil nach der ersten erfolgreichen Extraktion (Tab 'Konvertieren')."
        )
        return

    selected = st.selectbox("Profil auswählen", profiles)
    profile = _repo.load(selected)

    if profile is None:
        st.error("Profil konnte nicht geladen werden.")
        return

    col_view, col_edit = st.columns(2)

    with col_view:
        st.subheader("Profil-Details")
        st.json(profile)

    with col_edit:
        st.subheader("Profil bearbeiten")
        new_currency = st.text_input(
            "Typische Währung", value=profile.get("typical_currency", "EUR"),
        )
        new_discount = st.number_input(
            "Typischer Rabatt %", 0.0, 100.0,
            float(profile.get("typical_discount", 0.0)), 0.5,
        )
        new_hints = st.text_area("Spalten-Hinweise", value=profile.get("column_hints", ""))
        col_save, col_del = st.columns(2)
        with col_save:
            if st.button("Speichern", type="primary"):
                _repo.save(profile["name"], new_currency, new_discount, new_hints)
                st.success("Profil aktualisiert.")
                st.rerun()
        with col_del:
            if st.button("Profil löschen", type="secondary"):
                _repo.delete(selected)
                st.success(f"Profil '{selected}' gelöscht.")
                st.rerun()

    st.divider()
    st.subheader("Neues Profil anlegen")
    with st.form("new_profile_form"):
        np_name = st.text_input("Lieferantenname")
        np_currency = st.text_input("Typische Währung", value="EUR")
        np_discount = st.number_input("Typischer Rabatt %", 0.0, 100.0, 0.0, 0.5)
        np_hints = st.text_area("Spalten-Hinweise (optional)")
        submitted = st.form_submit_button("Profil erstellen")
        if submitted:
            if not np_name.strip():
                st.error("Lieferantenname darf nicht leer sein.")
            else:
                _repo.save(np_name.strip(), np_currency, np_discount, np_hints)
                st.success(f"Profil '{np_name}' erstellt.")
                st.rerun()
