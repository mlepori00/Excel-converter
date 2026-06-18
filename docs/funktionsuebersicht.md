# Offerten Converter – Funktionsübersicht

**Was das Tool heute zuverlässig kann · Stand: 12. Juni 2026 · AMP Sport GmbH**

Der Offerten Converter wandelt Lieferanten-Offerten (Excel/CSV) in standardisierte Reseller-Offerten um: Datei hochladen, Positionen automatisch erkennen lassen, Marge setzen, fertige Offerte als Excel exportieren – inklusive automatischem Archiv. Alle hier aufgeführten Funktionen sind durch 149 automatisierte Tests sowie manuelle Prüfung abgesichert.

## Der Ablauf in vier Schritten

| Schritt | Was passiert |
|---|---|
| 1 · Datei | Lieferanten-Offerte hochladen (Excel oder CSV) |
| 2 · Artikel | Positionen werden automatisch erkannt – bei Bedarf mit KI-Unterstützung |
| 3 · Offerte | Marke und Lieferant erfassen, Marge und Preise prüfen |
| 4 · Export | Standardisierte Reseller-Offerte als Excel laden – wird automatisch archiviert |

## 1 · Datei-Import

- **Formate:** Excel (.xlsx, .xls) und CSV werden direkt verarbeitet.
- **Mehrere Arbeitsblätter:** Bei Dateien mit mehreren Sheets wird automatisch das relevante Datenblatt vorgeschlagen; die Auswahl kann jederzeit geändert werden.
- **Intelligente Header-Erkennung:** Die Titelzeile wird auch dann gefunden, wenn sie nicht in Zeile 1 steht (z. B. nach Logo- oder Infozeilen).
- **Varianten-Matrizen:** Tabellen mit Grössen in Spalten (Grössenraster) werden automatisch in einzelne Positionen umgewandelt.
- **Verarbeitung nur im Arbeitsspeicher:** Hochgeladene Dateien werden nicht auf der Festplatte des Servers abgelegt.

## 2 · Automatische Artikel-Erkennung

- **Lokale Erkennung ohne KI-Kosten:** Rund 60 gängige Spaltenbezeichnungen (Deutsch und Englisch) wie SKU, EAN, Bezeichnung, Grösse, Farbe, EK/Stk, WHS oder Verfügbarkeit werden automatisch zugeordnet.
- **Preis-Fallback:** Fehlt die Einkaufspreis-Spalte, wird der Preis, wo möglich, aus Zusatzangaben (z. B. UVP/rrp) hergeleitet.
- **Währungserkennung:** Die Währung der Lieferanten-Offerte wird automatisch erkannt und vorausgewählt.
- **Wiedererkennung (Cache):** Eine bereits verarbeitete Datei ist beim erneuten Hochladen sofort da – ohne Wartezeit und ohne erneute KI-Kosten. Bei Bedarf: „Cache ignorieren & neu laden".

### KI-Unterstützung als Backup

- **Header analysieren (~ CHF 0.001):** Unbekannte Spaltennamen werden per KI den Standardfeldern zugeordnet – die günstige Zwischenstufe für ungewohnte Dateiformate.
- **Mit Claude extrahieren:** Vollständige KI-Extraktion als Rettungsanker für Dateien, die die automatische Erkennung nicht lesen kann. Der Button erscheint nur, wenn er gebraucht wird.
- **Kostentransparenz:** Vor jedem KI-Aufruf wird der geschätzte Betrag in CHF angezeigt.
- **Datenschutz:** Sensible Spalten (z. B. Kontaktdaten) werden vor jedem KI-Aufruf entfernt; der Lieferantenname wird nie an die KI übermittelt.

## 3 · Preise und Marge

- **Zwei Berechnungsmodi:** „EK + Marge" oder „Marktpreis" – pro Offerte umschaltbar.
- **Flexible Marge:** Standard-Marge für die ganze Offerte, pro Position überschreibbar; zusätzlich manueller Verkaufspreis je Position möglich.
- **Live-Berechnung:** VK pro Stück und VK Total werden bei jeder Eingabe sofort aktualisiert.
- **Währungsumrechnung:** EUR, USD und CHF mit tagesaktuellen EZB-Kursen.
- **Marktpreis-Recherche:** EAN-basierte Suche nach aktuellen Marktpreisen mit vorgängiger Stichprobe, Live-Fortschrittsanzeige und einstellbarem Abschlag in Prozent.
- **Filter:** Die Artikelliste lässt sich nach Bezeichnung, SKU, EAN, Farbe oder Grösse durchsuchen; exportiert wird, was angezeigt ist.

## 4 · Export und Archiv

- **Standardisierter Export:** Einheitliche, formatierte AMP-Excel-Offerte mit hinterlegten Formeln – bereit zum Versand.
- **Automatische Archivierung:** Jede exportierte Offerte wird automatisch gespeichert – inklusive Original-Lieferantendatei, erzeugter Offerte, Positionen und Metadaten.
- **Übersichtliche Ablage:** Navigation nach Jahr → Marke → Lieferant, ergänzt durch eine Freitextsuche.
- **Status-Workflow:** Erstellt → Versendet → Bestellung erhalten → Abgeschlossen – der Stand jeder Offerte ist jederzeit sichtbar und änderbar.
- **Vorschau im Browser:** Original- und erzeugte Excel-Datei lassen sich formatiert direkt im Browser ansehen – ohne Excel zu öffnen – und jederzeit herunterladen.
- **Saubere Stammdaten:** Marken- und Lieferantenvorschläge aus dem Archiv; bei ähnlichen Schreibweisen warnt das System vor Dubletten.

## Sicherheit und Benutzerverwaltung

- **Login mit E-Mail und Passwort:** Alle Funktionen sind erst nach Anmeldung zugänglich (Token-basiert, Sitzung 12 Stunden).
- **Kontrollierte Benutzerverwaltung:** Keine öffentliche Registrierung – Konten werden zentral durch den Administrator angelegt.
- **Erzwungener Passwortwechsel:** Neue Benutzer müssen ihr temporäres Passwort beim ersten Login ändern.
- **Sichere Speicherung:** Passwörter werden ausschliesslich verschlüsselt (bcrypt) gespeichert.

## Qualitätssicherung

- **149 automatisierte Tests** decken Einzelfunktionen, API-Schnittstellen und den kompletten Ablauf (Import → Erkennung → Preisberechnung → Export) ab – alle bestanden.
- **Durchgehend deutsche Oberfläche** mit geführtem 4-Schritte-Ablauf und einheitlichem, modernem Design.

## Bekannte Grenzen (Stand heute)

Der Vollständigkeit halber – folgende Punkte sind bewusst noch offen:

- Archivierte Offerten können angesehen und heruntergeladen, aber noch nicht direkt wieder zur Bearbeitung geöffnet werden (geplant: Phase 3).
- Beim Hochladen findet noch keine Vorprüfung von Dateigrösse und -typ statt.
- Tausendertrennzeichen werden in der Artikeltabelle noch nicht durchgehend schweizerisch formatiert.
