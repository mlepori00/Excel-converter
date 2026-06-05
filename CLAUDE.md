# Offerten Converter

Web-App (FastAPI + React) für Sportartikel-Distributoren: Lieferanten-Excel-Offerten hochladen → KI extrahiert Positionen → Marge setzen → standardisierte Reseller-Offerte als Excel exportieren.

## Architektur (Clean Architecture)

```
src/offerten_converter/
  domain/          → Entities (LineItem, SupplierProfile), Pricing-Logik (pure functions)
  application/     → Use Cases, Ports (abstrakte Interfaces)
  infrastructure/  → Claude/OpenRouter Extractors, Excel Reader/Writer, Profile Repo,
                     Column Mapper, Market Price Scraper, ECB Rates, Extraction Cache,
                     DB (SQLAlchemy engine/models/repos), Security (bcrypt + JWT)
  api/             → FastAPI Server (routes, auth, schemas, mappers, file_store) + Entry Point
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
