# Offerten Converter

Web-App (FastAPI + React) für Sportartikel-Distributoren: Lieferanten-Excel-Offerten hochladen → KI extrahiert Positionen → Marge setzen → standardisierte Reseller-Offerte als Excel exportieren.

## Architektur (Clean Architecture)

```
src/offerten_converter/
  domain/          → Entities (LineItem, SupplierProfile, User, Offer/OfferLine), Pricing-Logik (pure functions)
  application/     → Use Cases, Ports (abstrakte Interfaces)
  infrastructure/  → Claude/OpenRouter Extractors, Excel Reader/Writer, Profile Repo,
                     Column Mapper, Market Price Scraper, ECB Rates, Extraction Cache,
                     DB (SQLAlchemy engine/models/repos: User + Offer), Security (bcrypt + JWT)
  api/             → FastAPI Server (routes, auth, archive_routes, schemas, mappers, file_store) + Entry Point
frontend/          → React + Vite + TypeScript UI (kompiliert nach frontend/dist)
```

**Dependency Rule:** Innere Schichten importieren nie äussere. Domain kennt nichts ausser sich selbst. Application definiert Ports (ABCs); Infrastructure implementiert sie. Die `api/`-Schicht verdrahtet die Dependencies (DI) und exponiert HTTP-Endpunkte; das React-Frontend spricht ausschliesslich über diese API.

## Commands

```bash
# Backend (FastAPI) – Dev
$env:PYTHONPATH="src"; uvicorn offerten_converter.api.server:app --reload --port 8000

# Frontend (React/Vite) – Dev
cd frontend; npm run dev          # http://localhost:5173

# Production / Deployment (Backend serviert das gebaute Frontend)
docker compose up --build         # http://localhost:8000

# Benutzer anlegen (kein öffentliches Sign-up; nur via CLI)
$env:PYTHONPATH="src"; python -m offerten_converter.admin create-user --email a@b.ch --name "Anna"
$env:PYTHONPATH="src"; python -m offerten_converter.admin list-users

pytest                            # Alle Tests
pytest tests/unit                 # Nur Unit Tests
pytest -m integration             # Nur Integration Tests
ruff check src/ tests/            # Linting
```

## Auth & Persistenz

- Login per E-Mail/Passwort → JWT (Bearer). Jede `/api/*`-Route ausser `/api/auth/login` verlangt ein gültiges Token.
- Benutzer werden via `admin`-CLI angelegt (kein Self-Sign-up). `create-user` ohne `--password` erzeugt ein temporäres Passwort; der Nutzer muss es beim ersten Login ändern (`--no-force-change` für das eigene Konto).
- DB: SQLite via SQLAlchemy, Datei unter `./data/offerten.db` (über `DATABASE_URL` überschreibbar; in Docker als Volume gemountet). Schema-Erweiterungen vorerst als additive Mini-Migration in `init_db()` (Alembic geplant ab Phase 2).
- Env-Vars (siehe `.env.example`): `ANTHROPIC_API_KEY`, `SECRET_KEY` (JWT-Signatur, in Prod Pflicht), optional `DATABASE_URL`, `ACCESS_TOKEN_TTL_MINUTES`.

## Archiv

- Jede Offerte wird **automatisch beim Export** gespeichert (`POST /api/offer/export` → `X-Offer-Id`-Header). Gespeichert werden: Original-Lieferantendatei + erzeugte AMP-Excel (als Blob in der DB), bepreiste Positionen und Metadaten.
- **Ablage-Taxonomie:** Jahr → Marke → Lieferant (genau **eine Marke** pro Offerte; eine Marke kann mehrere Lieferanten haben). Kein Kundenfeld. Keine Migration von Altdaten.
- **Status-Workflow:** Erstellt → Versendet → Bestellung erhalten → Abgeschlossen (kein „Entwurf", da nur bei Export gespeichert).
- Tabellen: `offers` + `offer_line_items` (`OfferModel`/`OfferLineItemModel`). Datei-Blobs sind `deferred` (Listen/Detail laden sie nicht). `offer_line_items` hat bereits leere `provenance`-Spalten für den Round-Trip (Phase 3).
- **Vorschau:** `GET /api/offers/{id}/preview/{original|generated}` rendert die Excel serverseitig mit **openpyxl** zu einer formatierten HTML-Tabelle (`infrastructure/excel_html_renderer.py`, Port `SpreadsheetPreviewRenderer`) und liefert ein eigenständiges HTML-Dokument (`text/html`). Keine externe Render-Engine, plattformunabhängig; Zellwerte werden escaped (kein XSS), `.xls`/Fehlerfälle fallen auf eine einfache pandas-Tabelle zurück.
- Endpunkte (`api/archive_routes.py`, auth-geschützt): `GET /api/offers` (Filter `jahr/marke/lieferant/status/q`), `GET /api/offers/tree`, `GET /api/offers/{id}`, `PATCH /api/offers/{id}/status`, `GET /api/offers/{id}/original|generated`, `GET /api/offers/{id}/preview/{which}`.
- Frontend: Ansicht „Archiv" mit Jahr→Marke→Lieferant-Navigation, Suche, Detail, Status, Downloads sowie Tabellen-Spalten „Lieferanten-Offerte"/„Unsere Offerte" mit Gross-Vorschau (HTML in sandboxed `<iframe srcDoc>`). Wieder-Bearbeiten/Round-Trip folgt in Phase 3.

## Konventionen

- UI-Text: Deutsch | Code + Kommentare: Englisch
- Pricing-Logik lebt in `domain/pricing.py` – pure functions, keine Side Effects
- Sanitizer MUSS vor jedem API-Call laufen
- Lieferantenname wird nie an die API gesendet
- Dateien werden nur im Speicher verarbeitet (kein Disk-Write von Input-Dateien)
- Neue externe Abhängigkeiten: Port in `application/ports.py` definieren

## Testing

- Unit Tests: kein Filesystem, kein Netzwerk
- Integration Tests: `tmp_path` für Dateioperationen, Mocked AI für Extraktor; API-Routen via FastAPI `TestClient`
- E2E Tests: komplette Pipeline (sanitize → extract → price → export), AI gemockt
- Test-Fixtures in `tests/conftest.py`

## Branching (GitHub Flow)

- `main` ist immer deploybar
- Feature-Branches: `feature/<short-name>`
- PRs brauchen grüne CI vor Merge
