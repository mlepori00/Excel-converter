# Offerten Converter

A web app (FastAPI backend + React frontend) for sports distributors: upload a
supplier Excel quotation, let AI extract the line items, set your margin, and
export a formatted offer for your resellers – all in one step.

---

## Setup

### 1. Prerequisites
- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/)

### 2. Install dependencies

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure your API key

Copy `.env` and fill in your key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

**Never commit `.env` to version control.** It is already in `.gitignore`.

### 4. Run the app

Two terminals are needed — start both simultaneously:

**Terminal 1 – Python Backend (FastAPI)**
```powershell
$env:PYTHONPATH="src"; uvicorn offerten_converter.api.server:app --reload --port 8000
```

**Terminal 2 – React Frontend (Vite)**
```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173` in your browser.

> **Tip:** Run `pip install -e .` once to install the package in editable mode — then you can omit `$env:PYTHONPATH="src"` from the backend command.

---

## Data Flow – What stays local, what goes to Anthropic

```
Uploaded file (stays local, never written to disk)
    │
    ▼
pandas DataFrame
    │
    ▼
sanitize_data.py ──► strips: supplier name, customer names, email/phone/address,
    │                 IBAN, VAT-ID / UID-Nummer, any personal data
    │                 logs all removals locally for user review
    ▼
Sanitized product table (article names, prices, quantities, categories only)
    │
    ▼
Anthropic Claude API  ◄──── only this leaves your machine
    │
    ▼
Structured JSON (line items) ──► calculate_prices.py ──► excel_writer.py
                                  (local)                  (local)
```

### What stays entirely local
| Data | Location |
|------|----------|
| Uploaded Excel / CSV file | Memory only, never written to disk |
| Supplier name | Entered manually in UI, never sent to API |
| Customer names, addresses, contact info | Stripped by sanitizer before API call |
| IBAN, VAT-ID, UID-Nummer | Stripped by sanitizer |
| Supplier profiles | `/profiles/*.json` (column hints only, no pricing/PII) |
| Calculated prices & export file | Memory only, downloaded directly via browser |

### What is sent to the Anthropic API
Only the **sanitized product table** – a plain-text representation of article names,
prices, quantities, sizes, colors, and categories after all personal and identifying
information has been removed by the sanitizer.

### API log retention
Anthropic's API logs are automatically deleted after **7 days** and are not used to
train models for API customers. See [Anthropic's Privacy Policy](https://www.anthropic.com/privacy).

---

## Project Structure (Clean Architecture)

```
src/offerten_converter/
  domain/
    entities.py        # LineItem, SupplierProfile, QuotationSettings (dataclasses)
    pricing.py         # Pure functions: convert_to_target, calculate_vk, actual_margin
  application/
    ports.py           # Abstract interfaces (AIExtractor, ProfileRepository, ExcelWriter)
    sanitize_data.py   # PII/supplier-data removal before API call
    extract_products.py # AI extraction orchestration with chunking + JSON repair
    calculate_prices.py # Pricing enrichment (EK → VK with margin & currency)
    export_quotation.py # Excel export use case
    manage_profiles.py  # Supplier profile management use case
  infrastructure/
    ai_extractors/
      anthropic_extractor.py   # Anthropic direct adapter
      openrouter_extractor.py  # OpenRouter adapter
    column_mapper.py    # Claude-assisted column mapping
    market_price_scraper.py # Market price sampling from the web
    ecb_rates.py        # Currency exchange rates
    extraction_cache.py # Caches AI extraction results
    excel_reader.py     # Read Excel/CSV with smart header detection
    excel_writer.py     # Formatted openpyxl Excel output
    file_profile_repo.py # JSON file-based profile CRUD
  api/
    server.py           # FastAPI app + entry point (serves built frontend in prod)
    routes.py           # HTTP endpoints + dependency wiring
    schemas.py          # Pydantic request/response models
    mappers.py          # Domain <-> API schema mapping
    file_store.py       # In-memory upload handling
frontend/               # React + Vite + TypeScript UI (build output: frontend/dist)
profiles/               # Saved supplier profiles (.gitignored)
.env                    # API key (.gitignored)
```

**Dependency rule:** Inner layers never import outer layers. Domain knows nothing
but itself. Application defines ports (ABCs); infrastructure implements them.

---

## Usage

The app is a single screen built from cards:

1. **Import** – drag in or select an `.xlsx`, `.xls`, or `.csv` quotation.
   - If columns are detected automatically, the line items appear straight away.
   - Otherwise use **Header analysieren** (Claude-assisted column mapping) or
     **Extraktion starten** (full AI extraction) to pull out the line items.
2. **Review** – edit any cell in the product table and search/filter rows.
3. **Settings** – enter the supplier name, set the target margin % and currency,
   and choose the pricing mode (margin-based or market-based with a discount).
4. **Market prices** *(optional)* – sample or fetch market prices by EAN to
   benchmark or drive market-based pricing.
5. **Export** – download the formatted AMP Excel offer; an overview screen
   confirms supplier, article count, and currency.

Supplier profiles store only currency/discount defaults and column hints – no PII.

---

## Testing

```bash
pytest                   # All tests
pytest tests/unit        # Unit tests only
pytest -m integration    # Integration tests only
pytest -m e2e            # E2E tests only
ruff check src/ tests/   # Linting
```

---

## Security Notes

- API key is read exclusively from `.env` – never hardcoded or displayed in the UI
- Input files are processed in memory only; no file is written to disk
- Sanitizer runs before **every** API call, no exceptions
- `.gitignore` covers `.env`, `/profiles/`, `/uploads/`, `__pycache__`
