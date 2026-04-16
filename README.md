# Offerten Converter

A local Streamlit app for sports distributors: upload a supplier Excel quotation,
let AI extract the line items, set your margin, and export a formatted offer for
your resellers – all in one step.

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

```bash
streamlit run src/offerten_converter/main.py
```

Open `http://localhost:8501` in your browser.

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
  main.py              # Streamlit entry point + dependency wiring
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
    excel_reader.py     # Read Excel/CSV with smart header detection
    excel_writer.py     # Formatted openpyxl Excel output
    file_profile_repo.py # JSON file-based profile CRUD
  ui/
    state.py            # Session state initialization
    tab_konvertieren.py # Tab 1: Upload → Sanitize → Extract → Price → Export
    tab_lieferanten.py  # Tab 2: Supplier profile management
    tab_einstellungen.py # Tab 3: Settings (margins, currencies, rates)
profiles/               # Saved supplier profiles (.gitignored)
.env                    # API key (.gitignored)
```

**Dependency rule:** Inner layers never import outer layers. Domain knows nothing
but itself. Application defines ports (ABCs); infrastructure implements them.

---

## Usage

1. **Tab "Konvertieren"**
   - Enter supplier name manually
   - Optionally load a saved supplier profile
   - Upload `.xlsx`, `.xls`, or `.csv` quotation
   - Review sanitization log (what was removed)
   - Click "Extraktion starten" – Claude extracts all line items
   - Review and edit the extracted table
   - Set target margin % and currency in the sidebar
   - Check the live pricing preview (green/orange/red margin indicators)
   - Click "Export Offerte" to download the formatted Excel

2. **Tab "Lieferanten"**
   - View, edit, and delete saved supplier profiles
   - Profiles store only currency/discount defaults and column hints – no PII

3. **Tab "Einstellungen"**
   - Set company name (appears in Excel header)
   - Adjust default margin and currency
   - Update static currency exchange rates
   - Read the data-privacy summary

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
