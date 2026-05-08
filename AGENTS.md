# Offerten Converter

Streamlit-App für Sportartikel-Distributoren: Lieferanten-Excel-Offerten hochladen → KI extrahiert Positionen → Marge setzen → standardisierte Reseller-Offerte als Excel exportieren.

## Architektur (Clean Architecture)

```
src/offerten_converter/
  domain/          → Entities (LineItem, SupplierProfile), Pricing-Logik (pure functions)
  application/     → Use Cases, Ports (abstrakte Interfaces)
  infrastructure/  → Codex API Adapter, Excel Reader/Writer, File-based Profile Repository
  ui/              → Streamlit UI (Tabs, Session State)
  main.py          → Entry Point + Dependency Injection
```

**Dependency Rule:** Innere Schichten importieren nie äussere. Domain kennt nichts ausser sich selbst. Application definiert Ports (ABCs); Infrastructure implementiert sie.

## Commands

```bash
streamlit run src/offerten_converter/main.py   # App starten
pytest                                          # Alle Tests
pytest tests/unit                               # Nur Unit Tests
pytest -m integration                           # Nur Integration Tests
ruff check src/ tests/                          # Linting
```

## Konventionen

- UI-Text: Deutsch | Code + Kommentare: Englisch
- Pricing-Logik lebt in `domain/pricing.py` – pure functions, keine Side Effects
- Sanitizer MUSS vor jedem API-Call laufen
- Lieferantenname wird nie an die API gesendet
- Dateien werden nur im Speicher verarbeitet (kein Disk-Write von Input-Dateien)
- Neue externe Abhängigkeiten: Port in `application/ports.py` definieren

## Testing

- Unit Tests: kein Filesystem, kein Netzwerk, kein Streamlit
- Integration Tests: `tmp_path` für Dateioperationen, Mocked AI für Extraktor
- E2E Tests: komplette Pipeline (sanitize → extract → price → export), AI gemockt
- Test-Fixtures in `tests/conftest.py`

## Branching (GitHub Flow)

- `main` ist immer deploybar
- Feature-Branches: `feature/<short-name>`
- PRs brauchen grüne CI vor Merge
