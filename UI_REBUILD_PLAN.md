# AMP Sport UI Rebuild Plan

## Entscheidung

Die bestehende Backend-Logik bleibt erhalten. Die UI wird neu gebaut.

Der aktuelle Schmerz entsteht nicht in der Excel-, Preis- oder Exportlogik, sondern in der
Oberfläche. Die neue Richtung ist bewusst einfacher: keine Dashboard-App, kein Wizard, keine
Sidebar. Sales soll eine Offerte hineinziehen, eine kompakte Vorschau prüfen und die AMP-Offerte
als Excel herunterladen.

## Was Bleibt

- `src/offerten_converter/domain/`
- `src/offerten_converter/application/`
- `src/offerten_converter/infrastructure/`
- Excel-Reader
- Sanitizer
- KI-Extraktion
- Pricing
- Export
- Lieferantenprofile als Datenmodell
- Tests für Backend-Verhalten

## Was Neu Wird

- App-Shell
- Navigation
- kompletter 4-Schritt-Workflow
- Formularführung
- Tabellen- und Preisprüfung
- Export-Screen
- visuelles Designsystem
- UI-Komponenten
- Fehler-, Pflichtfeld- und Statuszustände

## Harte Produktregel

Die App muss für eine Person verständlich sein, die noch nie mit dem Offerten Converter
gearbeitet hat.

Jeder Screen beantwortet immer diese fünf Fragen:

1. Wo bin ich?
2. Was muss ich jetzt ausfüllen?
3. Was ist optional?
4. Warum kann ich noch nicht weiter?
5. Was passiert nach dem nächsten Klick?

## Zielbild

Das Zielbild orientiert sich am Stitch-Mockup:

- links eine klare Prozessnavigation
- oben eine ruhige AMP-Sport-Kopfleiste
- oben im Content ein 4-Schritt-Stepper
- in der Mitte eine grosse Arbeitsfläche
- rechts ein Kontextbereich mit Pflichtfeldern, Status und nächstem Schritt
- unten klare Primäraktion
- keine Landingpage
- keine dekorativen Marketing-Cards
- keine generische AI-SaaS-Optik
- keine Streamlit-Standard-Anmutung als Endzustand

## Zielarchitektur

### Empfohlener Weg

Die finale UI wird als echte Weboberfläche gebaut:

- Frontend: React + Vite
- UI: eigene AMP-Komponenten, kein generisches Dashboard-Kit
- Backend-Bridge: kleiner Python-API-Layer, der bestehende Use-Cases aufruft
- bestehende Domain/Application/Infrastructure bleiben die Quelle der Wahrheit

Warum:

- präzises Layout wie im Design möglich
- echte Sidebar/Header/Stepper-Kontrolle
- Datei-Upload kann professionell gestaltet werden
- Tabellen und Wizard-Zustände lassen sich sauber führen
- keine CSS-Kämpfe gegen Streamlit

### Übergang

Streamlit kann während des Rebuilds bestehen bleiben, wird aber nicht mehr als Ziel-UI
weiterentwickelt. Der neue UI-Pfad entsteht parallel und ersetzt die alte Oberfläche, sobald der
Workflow vollständig ist.

## Informationsarchitektur

### Hauptnavigation

Die Hauptnavigation besteht aus:

- Converter
- Lieferanten
- Einstellungen

Der Converter ist der zentrale Arbeitsbereich. Lieferanten und Einstellungen sind sekundär und
dürfen ruhiger und dichter sein.

### Converter Workflow

Der Converter ist eine Einseiten-Oberfläche mit drei sichtbaren Aktionen:

1. Datei hochladen
2. AMP-Offerte erstellen
3. Excel herunterladen

Produkterkennung, Sanitizer, Pricing und Exportlogik laufen im Hintergrund oder erscheinen nur
als kurze Bestätigung. Nutzer sollen nicht mit technischen Zwischenschritten belastet werden.

## Screen 1: Datei Vorbereiten

### Ziel

Eine Lieferantenofferte wird vorbereitet, ohne dass sensible Daten unnötig verarbeitet werden.

### Mitte

- Titel: `Offerte importieren`
- Feld: `Lieferant *`
- Feld: `Profil laden`
- Upload-Zone: `Lieferanten-Offerte hochladen`
- Datei-Metadaten nach Upload:
  - Dateiname
  - Grösse
  - erkannte Blätter
  - erkannte Währung
  - erkannte Struktur
- Primäraktion: `Produkte erkennen`

### Rechts

Pflichtfeldkarte:

- Lieferant: Missing/OK
- Excel-Datei: Missing/OK
- Profil: Optional

Nächster-Schritt-Karte:

- `02 Produkterkennung`
- kurze Erklärung, dass Artikelnummern, EANs, Preise, Varianten und Verfügbarkeiten erkannt werden

### Button-Logik

`Produkte erkennen` ist erst aktiv, wenn Lieferant und Datei gesetzt sind.

## Screen 2: Produkte Erkennen

### Ziel

Die App erklärt transparent, ob lokal, aus Cache oder per API extrahiert wird.

### Mitte

- Titel: `Produkte erkennen`
- Statusreihe:
  - Datei gelesen
  - Sanitizer aktiv
  - lokale Erkennung verfügbar
  - API nur nach Bestätigung
- Vorschau der erkannten Rohstruktur
- Primäraktion:
  - `Lokale Erkennung verwenden`, wenn möglich
  - `API-Extraktion starten`, wenn lokale Erkennung nicht reicht

### Rechts

Kontextkarte:

- Was wird an die API gesendet?
- Was bleibt lokal?
- geschätzte API-Kosten
- erwartete Anzahl Produkte

### Datenschutzregel

Lieferantenname wird nie an die API gesendet.

## Screen 3: Preise Prüfen

### Ziel

Die Tabelle ist das Hauptobjekt. Der Nutzer sieht sofort, welche Positionen unvollständig sind.

### Mitte

- Titel: `Preise prüfen`
- kompakte Toolbar:
  - Standard-Marge
  - Zielwährung
  - Marktpreis-Abschlag
  - auf alle anwenden
- grosse Produkttabelle
- Pflichtspalten visuell markiert:
  - Menge
  - EK/Stk
  - VK/Stk
- Zeilenstatus:
  - vollständig
  - Menge fehlt
  - Preis fehlt
  - Währung unbekannt

### Rechts

Preis-Checkkarte:

- Positionen gesamt
- Mengen fehlen
- Preise fehlen
- EK Total
- VK Total
- durchschnittliche Marge

### Primäraktion

`Export vorbereiten` ist erst aktiv, wenn alle Pflichtdaten exportfähig sind.

## Screen 4: Export Erstellen

### Ziel

Vor dem Download ist glasklar, was exportiert wird.

### Mitte

- Titel: `Export erstellen`
- Export-Zusammenfassung:
  - Lieferant
  - Anzahl Positionen
  - Zielwährung
  - Gültigkeit
  - Ersteller
- Dateiname-Vorschau
- Primäraktion: `Offerte herunterladen`

### Rechts

Bereitschaftskarte:

- Lieferant OK
- Positionen OK
- Mengen OK
- Preise OK
- Excel bereit

## Komponenten

### App Shell

- fixed left rail
- top header
- content stepper
- work surface
- right context rail
- footer optional, nur wenn genug Platz

### Buttons

- Primär: Navy background, weiss
- Sekundär: weiss, Navy border
- Disabled: grau, klar erkennbar

### Inputs

- hoher Kontrast
- Pflichtfelder mit `*`
- Missing-Zustand amber, nicht rot
- Hilfetext direkt unter dem Feld

### Status Chips

- `OK`
- `Missing`
- `Optional`
- `Lokal`
- `Cache`
- `API`
- `Exportbereit`

### Tabellen

- Header Navy
- kompakte Zeilen
- klare Zebra-Stripes
- Fehlerzustände pro Zeile
- keine Karten pro Produkt

## Design Tokens

Farben:

- Background: `#f7f9fb`
- Surface: `#ffffff`
- Surface low: `#f2f4f6`
- Navy: `#103080`
- Deep navy: `#001b5b`
- Cyan: `#30b0e0`
- Soft cyan: `#d8f0fb`
- Border: `#c5cbd6`
- Text: `#191c1e`
- Muted: `#6b7280`
- Warning: `#d97706`
- Success: `#15803d`

Typografie:

- Font: IBM Plex Sans oder Inter
- H1: 28-32px, 600
- H2: 22-24px, 600
- Body: 14-15px
- Labels: 11-12px, uppercase für Meta, normal für Formularfelder

Radius:

- Inputs/buttons: 4px
- Panels: 6-8px
- Tabellen: 0-4px

## Dateien Im Rebuild

Neue Struktur:

```text
src/offerten_converter/ui_new/
  app.py
  shell.py
  components.py
  workflow_state.py
  screens/
    prepare_file.py
    recognize_products.py
    review_prices.py
    export_offer.py
    suppliers.py
    settings.py
```

Wenn React/Vite umgesetzt wird:

```text
frontend/
  src/
    App.tsx
    shell/
    components/
    workflow/
    suppliers/
    settings/
    styles/
```

API-Bridge:

```text
src/offerten_converter/api/
  main.py
  schemas.py
  routes/
    offers.py
    profiles.py
    settings.py
```

## Umsetzung In Schnitten

### Aktueller Stand

Schnitt 1 wurde gestartet und die erste Contract-Schicht ist angelegt:

- `src/offerten_converter/api/schemas.py`
- `src/offerten_converter/api/mappers.py`
- `tests/unit/test_api_contracts.py`

Diese Schicht definiert JSON-fähige DTOs für den neuen Workflow, ohne FastAPI, React,
Streamlit oder zusätzliche Dependencies einzuführen.

Schnitt 2 wurde gestartet und die neue React/Vite-App-Shell ist angelegt:

- `frontend/package.json`
- `frontend/src/App.tsx`
- `frontend/src/components/AppShell.tsx`
- `frontend/src/components/Stepper.tsx`
- `frontend/src/components/RequirementPanel.tsx`
- `frontend/src/components/PrepareFileScreen.tsx`
- `frontend/src/styles/app.css`

Die Shell ist noch nicht mit dem Python-Backend verbunden. Sie nutzt Mock-State aus
`frontend/src/data/mockWorkflow.ts`, damit Layout, Zustände und Komponenten unabhängig vom
Backend sichtbar geprüft werden können.

### Schnitt 1: UI-Contract

- DTOs für Upload, Extract, Pricing und Export definieren
- klären, welche Backend-Funktionen direkt aufgerufen werden
- keine visuelle Arbeit

### Schnitt 2: App Shell

- Header
- Sidebar
- Stepper
- Layout-Raster
- responsive Desktop-Basis

### Schnitt 3: Datei Vorbereiten

- Lieferant
- Profil
- Upload
- Pflichtfeldlogik
- Datei-Metadaten

### Schnitt 4: Produkte Erkennen

- Sanitizer-Status
- Cache/lokal/API-Status
- Extraktionsaktion
- Ergebnisvorschau

### Schnitt 5: Preise Prüfen

- Toolbar
- Tabelle
- Validierung
- Metriken

### Schnitt 6: Export Erstellen

- Export-Check
- Download
- Fehlerzustände

### Schnitt 7: Lieferanten und Einstellungen

- Profile als echte Verwaltungsseite
- Settings als ruhige Formularseite

### Schnitt 8: QA

- Browser-Screenshot gegen Referenz
- Desktop und schmaler Viewport
- Upload mit Nike-Testdatei
- Export-Test
- `ruff`
- relevante `pytest` Tests

## Was Nicht Mehr Gemacht Wird

- keine weiteren kosmetischen Patches auf das alte Streamlit-UI
- keine neuen generischen Streamlit-Tabs als Hauptworkflow
- keine dekorativen Cards ohne Funktion
- keine unklare Button-Logik
- keine versteckten Pflichtfelder
- keine API-Aktion ohne sichtbaren Sanitizer-Kontext

## Erfolgskriterium

Der Rebuild ist erst erfolgreich, wenn eine neue Person ohne Erklärung versteht:

- Lieferant und Datei sind Pflicht
- Profil ist optional
- die Datei bleibt im Speicher
- der Sanitizer ist aktiv
- die API wird nicht heimlich verwendet
- Mengen müssen vor dem Export geprüft werden
- der Export ist erst bereit, wenn Pflichtdaten vollständig sind
