import { useMemo, useRef, useState } from "react";
import * as XLSX from "xlsx";

import { Icon } from "./components/Icon";

type Stage = "empty" | "uploaded" | "ready";

type PreviewRow = {
  sku: string;
  name: string;
  variant: string;
  qty: string;
  price: string;
  currency: string;
};

type ParsedOffer = {
  rows: PreviewRow[];
  totalRows: number;
  pricedRows: number;
  currency: string;
};

const emptyParsedOffer: ParsedOffer = {
  rows: [],
  totalRows: 0,
  pricedRows: 0,
  currency: "-"
};

const columnCandidates = {
  sku: ["sku", "artikel", "artikelnummer", "artikelnr", "code", "reference", "style"],
  name: ["product", "produkt", "name", "bezeichnung", "description", "style name", "model"],
  size: ["size", "grösse", "groesse", "größe", "grosse"],
  color: ["color", "colour", "farbe"],
  variant: ["variant", "variante"],
  qty: ["menge", "qty", "quantity", "available", "verfügbar", "verfuegbar", "stock", "bestand"],
  price: ["ek", "ek/stk", "preis", "price", "unit price", "offer price", "net price", "rrp", "whs"],
  currency: ["currency", "währung", "waehrung"]
};

function normalize(value: unknown): string {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function cleanCell(value: unknown): string {
  return String(value ?? "").replace(/\s+/g, " ").trim();
}

function findColumn(headers: unknown[], candidates: string[]): number {
  const normalizedCandidates = candidates.map(normalize);
  return headers.findIndex((header) => {
    const normalizedHeader = normalize(header);
    return normalizedCandidates.some((candidate) => normalizedHeader.includes(candidate));
  });
}

function cell(row: unknown[], index: number): string {
  if (index < 0) {
    return "";
  }
  return cleanCell(row[index]);
}

function parsePrice(value: string): string {
  if (!value) {
    return "";
  }
  const match = value.match(/(\d{1,3}(?:[.'\s]\d{3})*|\d+)([,.]\d{1,2})?/);
  if (!match) {
    return "";
  }
  const numeric = `${match[1]}${match[2] ?? ""}`
    .replace(/[.'\s]/g, "")
    .replace(",", ".");
  const parsed = Number(numeric);
  return Number.isFinite(parsed) ? parsed.toFixed(2) : "";
}

function findPriceInRow(row: unknown[], preferredIndex: number): string {
  const preferredPrice = parsePrice(cell(row, preferredIndex));
  if (preferredPrice) {
    return preferredPrice;
  }

  for (const value of row.map(cleanCell)) {
    const normalizedValue = normalize(value);
    const looksLikePrice =
      normalizedValue.includes("rrp") ||
      normalizedValue.includes("price") ||
      normalizedValue.includes("preis") ||
      value.includes("€") ||
      normalizedValue.includes("eur") ||
      normalizedValue.includes("chf") ||
      normalizedValue.includes("usd");

    if (!looksLikePrice) {
      continue;
    }

    const price = parsePrice(value);
    if (price) {
      return price;
    }
  }

  return "";
}

function detectCurrency(values: string[]): string {
  const joined = values.join(" ").toUpperCase();
  if (joined.includes("EUR") || joined.includes("€")) {
    return "EUR";
  }
  if (joined.includes("CHF")) {
    return "CHF";
  }
  if (joined.includes("USD")) {
    return "USD";
  }
  return "-";
}

function inferSupplierName(filename: string): string {
  const cleaned = filename
    .replace(/\.[^.]+$/, "")
    .replace(/\(\d+\)/g, "")
    .replace(/offerte/gi, "")
    .replace(/\d{6,}/g, "")
    .replace(/\b\d+\b/g, "")
    .replace(/[()_\-.]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  if (!cleaned) {
    return "";
  }

  return cleaned
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}

function findHeaderRow(rows: unknown[][]): number {
  let bestIndex = 0;
  let bestScore = -1;

  rows.slice(0, 30).forEach((row, index) => {
    const normalizedRow = row.map(normalize);
    const score = Object.values(columnCandidates).reduce((total, candidates) => {
      const normalizedCandidates = candidates.map(normalize);
      const hasCandidate = normalizedRow.some((header) =>
        normalizedCandidates.some((candidate) => header.includes(candidate))
      );
      return total + (hasCandidate ? 1 : 0);
    }, 0);
    const filledCells = row.filter((value) => cleanCell(value).length > 0).length;
    const weightedScore = score * 10 + Math.min(filledCells, 8);

    if (weightedScore > bestScore) {
      bestScore = weightedScore;
      bestIndex = index;
    }
  });

  return bestIndex;
}

async function parseOfferFile(file: File): Promise<ParsedOffer> {
  const buffer = await file.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: "array" });
  const sheet = workbook.Sheets[workbook.SheetNames[0]];
  const rawRows = XLSX.utils.sheet_to_json<unknown[]>(sheet, {
    blankrows: false,
    defval: "",
    header: 1
  });

  if (!rawRows.length) {
    return emptyParsedOffer;
  }

  const headerIndex = findHeaderRow(rawRows);
  const headers = rawRows[headerIndex] ?? [];
  const dataRows = rawRows
    .slice(headerIndex + 1)
    .filter((row) => row.filter((value) => cleanCell(value).length > 0).length >= 2);

  const skuIndex = findColumn(headers, columnCandidates.sku);
  const nameIndex = findColumn(headers, columnCandidates.name);
  const sizeIndex = findColumn(headers, columnCandidates.size);
  const colorIndex = findColumn(headers, columnCandidates.color);
  const variantIndex = findColumn(headers, columnCandidates.variant);
  const qtyIndex = findColumn(headers, columnCandidates.qty);
  const priceIndex = findColumn(headers, columnCandidates.price);
  const currencyIndex = findColumn(headers, columnCandidates.currency);

  const allText = rawRows.flat().map(cleanCell);
  const detectedCurrency = detectCurrency(allText);

  let pricedRows = 0;
  const previewRows = dataRows.slice(0, 8).map((row, index) => {
    const price = findPriceInRow(row, priceIndex);
    if (price) {
      pricedRows += 1;
    }

    const variantParts = [
      cell(row, variantIndex),
      cell(row, sizeIndex),
      cell(row, colorIndex)
    ].filter(Boolean);

    return {
      sku: cell(row, skuIndex) || cell(row, 0) || `Position ${index + 1}`,
      name: cell(row, nameIndex) || cell(row, 1) || "-",
      variant: [...new Set(variantParts)].join(" / ") || "-",
      qty: cell(row, qtyIndex) || "-",
      price: price || "-",
      currency: cell(row, currencyIndex) || detectedCurrency
    };
  });

  const totalPricedRows = dataRows.reduce((total, row) => {
    return total + (findPriceInRow(row, priceIndex) ? 1 : 0);
  }, 0);

  return {
    rows: previewRows,
    totalRows: dataRows.length,
    pricedRows: totalPricedRows || pricedRows,
    currency: detectedCurrency
  };
}

export default function App() {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [stage, setStage] = useState<Stage>("empty");
  const [fileName, setFileName] = useState("");
  const [supplierName, setSupplierName] = useState("");
  const [parsedOffer, setParsedOffer] = useState<ParsedOffer>(emptyParsedOffer);
  const [parseError, setParseError] = useState("");

  const supplierValue = supplierName.trim();
  const canExport = Boolean(fileName && supplierValue && parsedOffer.totalRows);

  const stats = useMemo(() => {
    if (!fileName) {
      return {
        positions: "-",
        currency: "-",
        prices: "-",
        status: "Wartet auf Offerte"
      };
    }

    return {
      positions: String(parsedOffer.totalRows || "-"),
      currency: parsedOffer.currency,
      prices: parsedOffer.pricedRows ? `${parsedOffer.pricedRows} erkannt` : "prüfen",
      status: parseError ? "Vorschau prüfen" : "Vorschau bereit"
    };
  }, [fileName, parseError, parsedOffer]);

  async function handleFile(file: File | undefined) {
    if (!file) {
      return;
    }
    setFileName(file.name);
    setSupplierName(inferSupplierName(file.name));
    setStage("uploaded");
    setParseError("");

    try {
      const parsed = await parseOfferFile(file);
      setParsedOffer(parsed);
      if (!parsed.totalRows) {
        setParseError("Keine Produktzeilen erkannt.");
      }
    } catch (error) {
      setParsedOffer(emptyParsedOffer);
      setParseError(error instanceof Error ? error.message : "Datei konnte nicht gelesen werden.");
    }
  }

  return (
    <main className="sales-app">
      <header className="site-header">
        <div className="brand">
          <span className="brand-symbol">AMP</span>
          <strong>AMP Sport</strong>
        </div>
        <div className="header-meta">
          <span>Offerten Converter</span>
          <span>Sanitizer aktiv</span>
        </div>
      </header>

      <section className="hero">
        <div>
          <p className="overline">Sales Tool</p>
          <h1>Offerte rein. AMP Offerte raus.</h1>
        </div>
        <p>
          Datei hineinziehen, Vorschau prüfen, Excel herunterladen. Keine Bearbeitung, kein
          unnötiger Workflow.
        </p>
      </section>

      <section className="converter-card">
        <div
          className={fileName ? "drop-zone has-file" : "drop-zone"}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            void handleFile(event.dataTransfer.files[0]);
          }}
        >
          <input
            accept=".xlsx,.xls,.csv"
            onChange={(event) => void handleFile(event.target.files?.[0])}
            ref={inputRef}
            type="file"
          />

          <div className="drop-art">
            <Icon name={fileName ? "check" : "upload"} size={42} />
          </div>
          <span className="drop-label">
            {fileName ? "Offerte geladen" : "Offerte hier hinziehen"}
          </span>
          <strong>{fileName || "Excel oder CSV hochladen"}</strong>
          <p>
            {fileName
              ? "Die Vorschau wird direkt aus der Datei gelesen."
              : "Die Originaldatei bleibt lokal im Prozess und wird für den AMP-Export vorbereitet."}
          </p>
          <button onClick={() => inputRef.current?.click()} type="button">
            {fileName ? "Datei ersetzen" : "Datei hochladen"}
          </button>
        </div>

        <aside className="preview-panel">
          <div className="panel-title">
            <span>Vorschau</span>
            <strong>{stats.status}</strong>
          </div>

          <label className="supplier-field">
            <span>Lieferant</span>
            <input
              onChange={(event) => setSupplierName(event.target.value)}
              placeholder="Lieferantenname"
              value={supplierName}
            />
          </label>

          <div className="stat-grid">
            <div>
              <span>Positionen</span>
              <strong>{stats.positions}</strong>
            </div>
            <div>
              <span>Währung</span>
              <strong>{stats.currency}</strong>
            </div>
            <div>
              <span>Preise</span>
              <strong>{stats.prices}</strong>
            </div>
          </div>

          {parseError ? <p className="parse-error">{parseError}</p> : null}

          <button
            className="export-button"
            disabled={!canExport}
            onClick={() => setStage("ready")}
            type="button"
          >
            AMP-Offerte erstellen
          </button>

          {stage === "ready" ? (
            <button className="download-button" type="button">
              Excel herunterladen
            </button>
          ) : null}
        </aside>
      </section>

      {stage !== "empty" ? (
        <section className="table-card">
          <div className="table-heading">
            <div>
              <span>Bestätigung</span>
              <h2>Erkannte Positionen</h2>
            </div>
            <button
              onClick={() => {
                setStage("empty");
                setFileName("");
                setSupplierName("");
                setParsedOffer(emptyParsedOffer);
                setParseError("");
                if (inputRef.current) {
                  inputRef.current.value = "";
                }
              }}
              type="button"
            >
              Neue Offerte
            </button>
          </div>

          <table>
            <thead>
              <tr>
                <th>Artikel</th>
                <th>Bezeichnung</th>
                <th>Variante</th>
                <th>Menge</th>
                <th>EK</th>
                <th>Währung</th>
              </tr>
            </thead>
            <tbody>
              {parsedOffer.rows.map((row, index) => (
                <tr key={`${row.sku}-${index}`}>
                  <td>{row.sku}</td>
                  <td>{row.name}</td>
                  <td>{row.variant}</td>
                  <td>{row.qty}</td>
                  <td>{row.price}</td>
                  <td>{row.currency}</td>
                </tr>
              ))}
              {!parsedOffer.rows.length ? (
                <tr>
                  <td colSpan={6}>Keine Vorschauzeilen erkannt.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </section>
      ) : null}
    </main>
  );
}
