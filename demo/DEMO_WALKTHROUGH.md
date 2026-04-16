# Demo-Walkthrough – Offerten Converter

**Ziel:** Zeigen, wie eine Lieferanten-Excel-Offerte in wenigen Klicks zur fertigen Reseller-Offerte wird.

**Demo-Datei:** `demo/Lieferanten_Offerte_SportPro_Demo.xlsx`

---

## App starten

```bash
streamlit run src/offerten_converter/main.py
```

Browser öffnet sich automatisch auf http://localhost:8501

---

## Ablauf (ca. 5–8 Minuten)

### Schritt 1 – Ausgangslage erklären (1 min)

> *„Wir bekommen von unseren Lieferanten Excel-Offerten in den unterschiedlichsten Formaten.
> Bisher musste man das alles manuell abtippen oder Copy-Paste machen.
> Diese App automatisiert das mit KI."*

Zeige kurz die Demo-Excel in Excel/LibreOffice:
- 37 Zeilen, verschiedene Produkte (Schuhe, Jacken, T-Shirts, Bags)
- Metadaten oben (Währung, Lieferant, Gültigkeitsdatum)
- Spalten: Artikelnummer, EAN, Bezeichnung, Farbe, Grösse, Preis, Rabatt usw.

---

### Schritt 2 – Tab „Konvertieren" (Hauptflow)

#### 2a. Lieferant eingeben
- Feld „Lieferantenname" → **`SportPro Demo`** eingeben
- *(Hinweis: Dieser Name wird nie an die API gesendet – Datenschutz)*

#### 2b. Datei hochladen
- Auf **„Browse files"** klicken → `demo/Lieferanten_Offerte_SportPro_Demo.xlsx` auswählen
- App zeigt: *„37 Zeilen, 11 Spalten"*

#### 2c. Datenschutz-Bereinigung
- App zeigt automatisch an, welche Spalten entfernt oder geschwärzt wurden
- Bei unserer Demo-Datei: Kontaktperson-Spalte wird bereinigt
- Erklären: *„Bevor irgend etwas an Claude gesendet wird, werden alle persönlichen Daten entfernt."*

#### 2d. KI-Extraktion
- Geschätzte Kosten werden angezeigt (bei dieser Demo: Bruchteile eines Rappen)
- Auf **„Extraktion starten"** klicken
- Claude liest die bereinigte Tabelle und extrahiert alle Felder strukturiert:
  SKU, EAN, Produktname, Grösse, Farbe, Preis, Währung, Rabatt usw.
- Ergebnis: ~37 extrahierte Positionen als editierbare Tabelle

#### 2e. Tabelle prüfen & bearbeiten
- Zeige, dass man direkt in der Tabelle Werte korrigieren kann
- z.B. eine Menge oder einen Preis anpassen

---

### Schritt 3 – Kalkulation (1 min)

In der **Sidebar** links:
- Marge auf z.B. **45%** setzen
- Zielwährung: **CHF**

Die Kalkulations-Tabelle aktualisiert sich sofort:
- **EK** (Einkaufspreis, umgerechnet in CHF)
- **VK** (Verkaufspreis mit Marge)
- Margen-Farben: grün = OK, orange = knapp, rot = zu tief
- Zusammenfassung: Total EK / Total VK / Ø Marge

> *„Wenn ein Lieferant in EUR liefert, werden aktuelle Wechselkurse automatisch bezogen."*

---

### Schritt 4 – Export (30 sek)

- Auf **„Export Offerte (.xlsx)"** klicken
- Datei `Offerte_SportPro_Demo_DATUM.xlsx` wird heruntergeladen
- Kurz zeigen: professionell formatiertes Excel mit Firmenname, Gültigkeitsdatum, allen Preisen

---

### Schritt 5 – Lieferantenprofile (optional, 1 min)

Tab **„Lieferanten"** zeigen:
- Profil für SportPro anlegen (Währung EUR, typischer Rabatt 15%, Spaltenhinweise)
- Beim nächsten Upload kann man das Profil laden → Claude weiss schon, wie die Spalten heissen

---

### Schritt 6 – Einstellungen (optional, 30 sek)

Tab **„Einstellungen"** zeigen:
- Standard-Marge festlegen
- Zielwährung wählen
- Firmenname für den Export-Header

---

## Mögliche Fragen & Antworten

**„Was kostet das pro Offerte?"**
> Wenige Rappen pro Extraktion (je nach Dateigrösse). Bei 37 Zeilen ca. CHF 0.002–0.01.

**„Funktioniert das mit allen Excel-Formaten?"**
> Ja – zusammengeführte Zellen, verschiedene Header-Positionen, CSV.
> Sogar Pivot-Tabellen (z.B. Grössen als Spalten) werden automatisch umgewandelt.

**„Gehen die Lieferantendaten zu Anthropic/Claude?"**
> Nur die bereinigten Produktdaten (Artikelnummern, Preise, Grössen).
> Lieferantenname, Kontaktpersonen und persönliche Infos werden vorher automatisch entfernt.

**„Kann man das für verschiedene Lieferanten nutzen?"**
> Ja, mit Lieferantenprofilen kann man Formathinweise speichern, damit die KI-Extraktion
> beim nächsten Mal noch besser funktioniert.

---

## Technischer Hintergrund (falls gefragt)

- **Streamlit** – Python Web-Framework, läuft lokal im Browser
- **Claude (Anthropic)** – KI-Modell für die Extraktion (via OpenRouter)
- **Clean Architecture** – Domain / Application / Infrastructure getrennt, einfach erweiterbar
- **Kein Speichern auf Disk** – Dateien werden nur im Speicher verarbeitet
