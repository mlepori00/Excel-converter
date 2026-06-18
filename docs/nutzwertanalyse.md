# Nutzwertanalyse – Offerten Converter

**Zweck:** Use-Case-Katalog zur Priorisierung mit der Geschäftsleitung.
**So nutzen:** Spalte **Nutzen (1–5)** gemeinsam ausfüllen (5 = geschäftskritisch). `Nutzen ÷ Aufwand` ergibt die Reihenfolge der Umsetzung.

**Legende Status:** ✅ vorhanden · 🟡 geplant (Roadmap, noch nicht gebaut) · 🆕 neu (noch nirgends)
**Legende Aufwand:** S = klein · M = mittel · L = gross

---

## Der Gesamt-Ablauf (Soll)

```
Lieferanten-Offerte (Excel)
   │  ① App parst & bringt in AMP-Format
   ▼
Aufbereitung: Marktpreise, Margen, Lieferanten-Vergleich, Kunden-Festpreise
   │  ② Kundenofferte erzeugen
   ▼
Kunde wählt Mengen → sendet zurück
   │  ③ App bringt Bestellung zurück ins Original-Lieferanten-Format (Round-Trip)
   ▼
Bestellung an Lieferant → Ware kommt
   │  ④ alles sauber archiviert + auswertbar
```

---

## A · Erfassung & Parsing der Lieferanten-Offerte

| Nr | Use Case | Heute | Aufwand | Nutzen (1–5) |
|----|----------|:-----:|:-------:|:------------:|
| A1 | Die App liest eine Lieferanten-Excel ein und extrahiert die Positionen (KI). | ✅ | – | |
| A2 | Die App bringt die Positionen automatisch in unser einheitliches AMP-Format. | ✅ | – | |
| A3 | Der Lieferantenname wird manuell erfasst und nie an die KI gesendet (Datenschutz). | ✅ | – | |
| A4 | Die App erkennt die Spalten der Lieferanten-Offerte automatisch (Heuristik + KI). | ✅ | – | |
| A5 | Dateien werden nur im Speicher verarbeitet, nicht auf Platte geschrieben. | ✅ | – | |
| A6 | Die App entpivotiert Grössen-/Farbmatrizen korrekt in einzelne Positionen. | ✅ | – | |
| A7 | 💡 Die App warnt, wenn Pflichtfelder (z. B. EAN) in vielen Zeilen fehlen. | 🆕 | S | |

## B · Aufbereitung, Preise & Vergleiche

| Nr | Use Case | Heute | Aufwand | Nutzen (1–5) |
|----|----------|:-----:|:-------:|:------------:|
| B1 | Die App zeigt Marktpreise zu jedem Artikel (Suche per EAN). | ✅ | – | |
| B2 | Die App rechnet Fremdwährungen in unsere Zielwährung um (CHF). | ✅ | – | |
| B3 | Der Einkäufer setzt eine Marge (pauschal oder pro Position); VK wird berechnet. | ✅ | – | |
| B4 | Die App warnt farblich bei zu tiefer Marge (orange/rot). | ✅ | – | |
| B5 | Die App kann den VK aus dem Marktpreis ableiten (Rabatt auf Marktpreis). | ✅ | – | |
| B6 | **Die App vergleicht für denselben Artikel die Preise aller Lieferanten einer Marke** und zeigt, wer am günstigsten ist. | 🆕 | M | |
| B7 | 💡 Die App zeigt die **Preis-Historie** eines Artikels über die Jahre (Verhandlungsbasis). | 🆕 | M | |
| B8 | 💡 Die App markiert je Artikel automatisch den **besten Lieferanten** (Preis + Verfügbarkeit). | 🆕 | M | |
| B9 | 💡 Die App zeigt die erzielte Marge **gegenüber dem Marktpreis** (nicht nur ggü. EK). | 🆕 | S | |
| B10 | 💡 Die App zeigt die **Verfügbarkeit** (Max. Menge) im Lieferantenvergleich mit an. | 🆕 | S | |
| B11 | 💡 Die App warnt bei **Dubletten** (gleicher Artikel mehrfach / über Lieferanten). | 🆕 | S | |

## C · Kundenofferte erstellen & versenden

| Nr | Use Case | Heute | Aufwand | Nutzen (1–5) |
|----|----------|:-----:|:-------:|:------------:|
| C1 | Die App erzeugt eine versandfertige Kundenofferte als Excel (eigenes Format). | ✅ | – | |
| C2 | Der eigene Einkaufspreis (EK) ist in der Kundenofferte nie sichtbar. | ✅ | – | |
| C3 | In der Kundenofferte ist die Spalte „Bestellt" leer und vom Kunden ausfüllbar. | ✅ | – | |
| C4 | Die App verhindert per Excel-Regel, dass der Kunde mehr bestellt als verfügbar. | ✅ | – | |
| C5 | 💡 Die App ordnet jede Offerte einem **Kunden** zu (Empfänger). | 🆕 | M | |
| C6 | 💡 Die App hinterlegt eine **Gültigkeitsfrist** der Offerte und erinnert vor Ablauf. | 🆕 | M | |
| C7 | 💡 Die Kundenofferte trägt kunden­spezifisches Branding (Logo/Kopf). | 🆕 | S | |

## D · Rücklauf & Round-Trip (Bestellung → Lieferant)

| Nr | Use Case | Heute | Aufwand | Nutzen (1–5) |
|----|----------|:-----:|:-------:|:------------:|
| D1 | Der Kunde sendet die ausgefüllte Offerte zurück; die App liest die Mengen ein. | 🟡 | L | |
| D2 | **Die App bringt die Kundenbestellung zurück ins Original-Lieferanten-Format.** | 🟡 | L | |
| D3 | Die App merkt sich je Position die Herkunftszelle der Original-Datei (für D2). | 🟡 | L | |
| D4 | Die App erzeugt die Bestellung an den Lieferanten als versandfertige Datei. | 🟡 | M | |

## E · Lieferanten-Stammdaten & Abmachungen

| Nr | Use Case | Heute | Aufwand | Nutzen (1–5) |
|----|----------|:-----:|:-------:|:------------:|
| E1 | Pro Marke können mehrere Lieferanten geführt werden. | ✅ (als Freitext) | – | |
| E2 | **Die App führt echte Lieferanten-Stammdaten** (Kontakt, Adresse). | 🆕 | M | |
| E3 | Die App hinterlegt **Konditionen/Abmachungen** je Lieferant (Rabatt, Zahlungsziel, Skonto, Lieferzeit, Mindestbestellwert). | 🆕 | M | |
| E4 | 💡 Die App **importiert Lieferantendaten aus dem ERP** (Einweg-Import, kein Live-Sync). | 🆕 | M | |
| E5 | Die App speichert je Lieferant Extraktions-Hilfen (Spalten-Hinweise) für besseres Parsing. | ✅ (Datei-Profile) | – | |

## F · Kunden-Stammdaten & Festpreise

| Nr | Use Case | Heute | Aufwand | Nutzen (1–5) |
|----|----------|:-----:|:-------:|:------------:|
| F1 | **Die App führt Kunden-Stammdaten** (Kontakt, Adresse). | 🆕 | M | |
| F2 | **Die App hinterlegt feste/verhandelte Preise je Kunde und Artikel** und wendet sie automatisch an. | 🆕 | L | |
| F3 | Die App zeigt beim Erstellen, welcher Preis ein Kunde bisher für einen Artikel zahlte (Historie). | 🆕 | M | |
| F4 | Die App warnt, wenn ein neuer VK vom hinterlegten Festpreis des Kunden abweicht. | 🆕 | S | |
| F5 | 💡 Die App **importiert Kundendaten aus dem ERP** (Einweg-Import). | 🆕 | M | |

## G · Lager / Eigenbestand

| Nr | Use Case | Heute | Aufwand | Nutzen (1–5) |
|----|----------|:-----:|:-------:|:------------:|
| G1 | Die App trennt je Position **Kundenmenge** und **Eigen-/Lagermenge** (auf Vorrat gekauft). | 🆕 | M | |
| G2 | Die App bestellt beim Lieferanten Kunden- + Lagermenge gebündelt, weist beides aber getrennt aus. | 🆕 | M | |
| G3 | 💡 Die App führt einen einfachen **Lagerbestand** der eingekauften Eigen-Ware. | 🆕 | L | |

## H · Archiv & Dokumentenablage

| Nr | Use Case | Heute | Aufwand | Nutzen (1–5) |
|----|----------|:-----:|:-------:|:------------:|
| H1 | Die App **legt alle Dokumente automatisch sauber ab** (beim Export). | ✅ | – | |
| H2 | Gespeichert werden Original-Lieferantendatei **und** erzeugte AMP-Datei + Positionen. | ✅ | – | |
| H3 | Ablage-Navigation nach **Jahr → Marke → Lieferant**. | ✅ | – | |
| H4 | Volltext-Suche & Filter (Jahr/Marke/Lieferant/Status) im Archiv. | ✅ | – | |
| H5 | Status-Verlauf je Offerte: Erstellt → Versendet → Bestellung erhalten → Abgeschlossen. | ✅ | – | |
| H6 | Gross-Vorschau beider Excel-Dateien direkt im Browser. | ✅ | – | |
| H7 | Erneuter Download beider Dateien jederzeit möglich. | ✅ | – | |
| H8 | 💡 Ablage zusätzlich nach **Saison/Kollektion** (HS/FS), nicht nur Kalenderjahr. | 🆕 | S | |
| H9 | 💡 Optionaler **Spiegel/Backup** auf OneDrive (DB bleibt führend). | 🆕 | M | |

## I · Auswertungen & Reporting 💡

| Nr | Use Case | Heute | Aufwand | Nutzen (1–5) |
|----|----------|:-----:|:-------:|:------------:|
| I1 | Die App wertet **Umsatz/Marge je Marke, Lieferant, Kunde, Saison** aus. | 🆕 | M | |
| I2 | Die App zeigt, welche Lieferanten über die Zeit die besten Konditionen boten. | 🆕 | M | |
| I3 | Die App zeigt offene Offerten / ausstehende Kundenrückläufe auf einen Blick (Dashboard). | 🆕 | M | |
| I4 | Die App exportiert Auswertungen als Excel/PDF. | 🆕 | S | |

## J · Benutzer, Rechte & Zusammenarbeit

| Nr | Use Case | Heute | Aufwand | Nutzen (1–5) |
|----|----------|:-----:|:-------:|:------------:|
| J1 | Login pro Person (E-Mail/Passwort); alle `/api`-Zugriffe geschützt. | ✅ | – | |
| J2 | Alle berechtigten Nutzer sehen/bearbeiten dasselbe gemeinsame Archiv. | ✅ | – | |
| J3 | Je Offerte ist nachvollziehbar, **wer sie erstellt** hat. | ✅ | – | |
| J4 | Benutzer werden nur durch eine Admin-Person angelegt (kein offenes Sign-up). | ✅ | – | |
| J5 | 💡 Rollen/Rechte (z. B. nur Lesen vs. Bearbeiten vs. Admin). | 🆕 | M | |
| J6 | 💡 Hinweis „zuletzt bearbeitet von X" bei gleichzeitigem Zugriff. | 🆕 | S | |

## K · Datenschutz, Hosting & Betrieb

| Nr | Use Case | Heute | Aufwand | Nutzen (1–5) |
|----|----------|:-----:|:-------:|:------------:|
| K1 | Die KI-Extraktion läuft datenschutzkonform (EU/CH-Route, AVV/DPA) – relevant wegen Kundendaten (revDSG). | 🟡 offen | M | |
| K2 | Die App läuft „per Link" auf einem Server; Kollegen brauchen kein lokales Setup. | 🟡 offen | M | |
| K3 | Hosting-Standort wählbar (CH/EU) für maximalen Datenschutz. | 🟡 offen | – | |
| K4 | Regelmässige, wiederherstellbare **Backups** der Datenbank. | 🟡 offen | S | |
| K5 | 💡 Protokoll/Audit, wer wann welche Daten geändert hat (bei Kundendaten oft Pflicht). | 🆕 | M | |

---

## Offene Fragen / Annahmen für die Besprechung

1. **Artikel-Identität:** Woran erkennen wir „denselben Artikel" über Lieferanten/Jahre? (Empfehlung: EAN primär, SKU/Name als Fallback.) → entscheidet, wie gut B6–B8 und F2 funktionieren.
2. **Kunden-Festpreis = Verkaufspreis an den Kunden** (das, was er uns zahlt), nicht der EK. Korrekt so?
3. **Eine Marke pro Offerte** ist heute fix. Gibt es Lieferanten-Offerten mit mehreren Marken? → ggf. Modell anpassen.
4. **MwSt / Rundung / Preiseinheiten:** Müssen in Kundenofferten Steuer/Rundungsregeln abgebildet werden?
5. **ERP:** Welches System, und kann es EAN-basiert exportieren (für E4/F5)?
6. **Datenschutz:** Sobald echte Kundendaten gespeichert werden, greift revDSG → Hosting-Standort + KI-Route müssen vorher geklärt sein.

---

## Kurzfazit (Stand heute)

- **Block A, C (Grundlagen), H, J sind weitgehend fertig.** Das Fundament steht.
- **Round-Trip (D1–D4)** ist als nächster grosser Brocken bereits geplant.
- **Lieferantenvergleich (B6–B8)** ist viel günstiger als es klingt, weil die Preisdaten im Archiv schon vorliegen → grosser Nutzen bei mittlerem Aufwand.
- **Kunden + Festpreise (F)** ist der grösste neue Block (berührt Kern-Preislogik + Datenschutz).
- **Datenschutz & Hosting (K)** sind die echten Vorbedingungen, sobald Kundendaten ins Spiel kommen.
