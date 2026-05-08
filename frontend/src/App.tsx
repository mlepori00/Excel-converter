import { useRef, useState } from "react";

import { Icon } from "./components/Icon";

const API = "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types matching the FastAPI response models
// ---------------------------------------------------------------------------

type Stage = "empty" | "parsing" | "parsed" | "extracting" | "ready" | "exporting";

type ProductRow = {
  row_id: number;
  sku: string | null;
  ean: string | null;
  product_name: string | null;
  size: string | null;
  color: string | null;
  category: string | null;
  unit_price: number | null;
  currency: string | null;
  ordered_qty: number | null;
  available_qty: number | null;
  discount_pct: number | null;
  notes: string | null;
  status: string;
};

type ParseResult = {
  file_id: string;
  filename: string;
  sheets: string[];
  selected_sheet: string | null;
  row_count: number;
  column_count: number;
  detected_currency: string | null;
  layout_type: string | null;
  was_unpivoted: boolean;
  sanitizer_removed: number;
  extraction_mode: string;
  products: ProductRow[];
  api_cost_estimate_chf: number | null;
};

// Local edits the user makes in the pricing table
type RowEdit = {
  ordered_qty: number | null;
  vk_manual: number | null;
  margin_pct: number;
};

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function apiParse(file: File, forceReparse = false): Promise<ParseResult> {
  const form = new FormData();
  form.append("file", file);
  if (forceReparse) form.append("force_reparse", "true");
  const resp = await fetch(`${API}/api/offer/parse`, { method: "POST", body: form });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail ?? "Parse-Fehler");
  }
  return resp.json() as Promise<ParseResult>;
}

async function apiExtract(fileId: string, profileName?: string): Promise<ProductRow[]> {
  const resp = await fetch(`${API}/api/offer/extract`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_id: fileId, force_api: true, profile_name: profileName ?? null }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail ?? "Extraktions-Fehler");
  }
  const data = await resp.json() as { products: ProductRow[] };
  return data.products;
}

async function apiExport(
  fileId: string,
  supplierName: string,
  targetCurrency: string,
  defaultMargin: number,
  products: ProductRow[],
  edits: Record<number, RowEdit>,
  marketPrices: Record<string, number>
): Promise<Blob> {
  const rows = products.map((p) => {
    const edit = edits[p.row_id] ?? { ordered_qty: null, vk_manual: null, margin_pct: defaultMargin };
    return {
      sku: p.sku,
      ean: p.ean,
      product_name: p.product_name,
      size: p.size,
      color: p.color,
      category: p.category,
      unit_price: p.unit_price,
      currency: p.currency,
      discount_pct: p.discount_pct,
      notes: p.notes,
      available_qty: p.available_qty,
      ordered_qty: edit.ordered_qty,
      vk_manual: edit.vk_manual,
      margin_pct: edit.margin_pct,
      market_price: p.ean ? (marketPrices[p.ean] ?? null) : null,
    };
  });

  const resp = await fetch(`${API}/api/offer/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      file_id: fileId,
      supplier_name: supplierName,
      created_by: "AMP Sport GmbH",
      target_currency: targetCurrency,
      valid_days: 30,
      default_margin_pct: defaultMargin,
      rows,
    }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail ?? "Export-Fehler");
  }
  return resp.blob();
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

export default function App() {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const scrapeAbortRef = useRef<AbortController | null>(null);
  const fileRef = useRef<File | null>(null);

  const [stage, setStage] = useState<Stage>("empty");
  const [error, setError] = useState("");

  const [parseResult, setParseResult] = useState<ParseResult | null>(null);
  const [products, setProducts] = useState<ProductRow[]>([]);
  const [edits, setEdits] = useState<Record<number, RowEdit>>({});

  const [supplierName, setSupplierName] = useState("");
  const [margin, setMargin] = useState(40);
  const [targetCurrency, setTargetCurrency] = useState("CHF");
  const [marketPrices, setMarketPrices] = useState<Record<string, number>>({});
  const [scrapingStatus, setScrapingStatus] = useState("");
  const [scrapingProgress, setScrapingProgress] = useState<{ done: number; total: number } | null>(null);

  const [pricingMode, setPricingMode] = useState<"margin" | "market">("margin");
  const [marketDiscount, setMarketDiscount] = useState(20);
  const [scrapeEnabled, setScrapeEnabled] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const needsAiExtraction =
    parseResult !== null && parseResult.extraction_mode === "none" && products.length === 0;

  const canExport =
    stage === "ready" && supplierName.trim() !== "" && products.length > 0;

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  async function loadMarketPrices(rows: ProductRow[]) {
    const eans = rows
      .map((r) => r.ean?.trim() ?? "")
      .filter((e) => e.length > 0);
    if (eans.length === 0) return;

    // Cancel any running scrape for a previous file
    scrapeAbortRef.current?.abort();
    const controller = new AbortController();
    scrapeAbortRef.current = controller;

    setScrapingProgress({ done: 0, total: eans.length });
    setScrapingStatus("");
    setMarketPrices({});

    let resp: Response;
    try {
      resp = await fetch(`${API}/api/offer/market-prices/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ eans }),
        signal: controller.signal,
      });
    } catch {
      if (controller.signal.aborted) return;
      setScrapingProgress(null);
      setScrapingStatus("Marktpreis-Abfrage fehlgeschlagen");
      return;
    }

    if (!resp.ok || !resp.body) {
      setScrapingProgress(null);
      setScrapingStatus("Marktpreis-Abfrage fehlgeschlagen");
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    const prices: Record<string, number> = {};

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const ev = JSON.parse(line.slice(6)) as {
              ean: string;
              price: number | null;
              done: number;
              total: number;
              finished: boolean;
            };
            if (ev.price != null) prices[ev.ean] = ev.price;
            setScrapingProgress({ done: ev.done, total: ev.total });
            setMarketPrices({ ...prices });
            if (ev.finished) {
              const found = Object.keys(prices).length;
              setScrapingStatus(
                found > 0
                  ? `${found} von ${ev.total} Marktpreise gefunden`
                  : "Keine Marktpreise gefunden"
              );
              setScrapingProgress(null);
            }
          } catch {
            // malformed SSE line – skip
          }
        }
      }
    } catch {
      if (controller.signal.aborted) return; // new file loaded – silently stop
      setScrapingProgress(null);
      setScrapingStatus("Marktpreis-Abfrage unterbrochen");
    }
  }

  async function handleFile(file: File | undefined) {
    if (!file) return;
    fileRef.current = file;
    scrapeAbortRef.current?.abort();
    setError("");
    setStage("parsing");
    setParseResult(null);
    setProducts([]);
    setEdits({});

    try {
      const result = await apiParse(file);
      setParseResult(result);
      if (result.products.length > 0) {
        setProducts(result.products);
        setStage("ready");
        if (scrapeEnabled) void loadMarketPrices(result.products);
      } else {
        // No local/cache extraction – need Claude
        setStage("parsed");
      }
      if (!supplierName.trim()) {
        setSupplierName(inferSupplierName(file.name));
      }
      if (result.detected_currency) {
        setTargetCurrency(result.detected_currency);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unbekannter Fehler");
      setStage("empty");
    }
  }

  async function handleReparse() {
    if (!fileRef.current) return;
    scrapeAbortRef.current?.abort();
    setError("");
    setStage("parsing");
    setProducts([]);
    setEdits({});
    setMarketPrices({});
    setScrapingStatus("");
    setScrapingProgress(null);
    try {
      const result = await apiParse(fileRef.current, true);
      setParseResult(result);
      if (result.products.length > 0) {
        setProducts(result.products);
        setStage("ready");
        if (scrapeEnabled) void loadMarketPrices(result.products);
      } else {
        setStage("parsed");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Fehler beim Neu-Laden");
      setStage("ready");
    }
  }

  async function handleExtract() {
    if (!parseResult) return;
    setError("");
    setStage("extracting");
    try {
      const rows = await apiExtract(parseResult.file_id);
      setProducts(rows);
      setStage("ready");
      if (scrapeEnabled) void loadMarketPrices(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Extraktions-Fehler");
      setStage("parsed");
    }
  }

  async function handleExport() {
    if (!parseResult || !canExport) return;
    setError("");
    setStage("exporting");
    try {
      // When in market-price mode, inject vk_manual from scraped prices
      // (only for rows without an existing manual override)
      let effectiveEdits = edits;
      if (pricingMode === "market") {
        const overrides: Record<number, RowEdit> = {};
        products.forEach((p) => {
          const existing = edits[p.row_id];
          if (existing?.vk_manual != null) return;
          const mp = p.ean ? marketPrices[p.ean] : undefined;
          if (mp != null) {
            overrides[p.row_id] = {
              ordered_qty: existing?.ordered_qty ?? null,
              vk_manual: parseFloat((mp * (1 - marketDiscount / 100)).toFixed(2)),
              margin_pct: existing?.margin_pct ?? margin,
            };
          }
        });
        effectiveEdits = { ...edits, ...overrides };
      }

      const blob = await apiExport(
        parseResult.file_id,
        supplierName.trim(),
        targetCurrency,
        margin,
        filteredProducts,
        effectiveEdits,
        marketPrices
      );
      const today = new Date().toISOString().slice(0, 10).replace(/-/g, "");
      downloadBlob(blob, `Offerte_${supplierName.trim().replace(/\s+/g, "_")}_${today}.xlsx`);
      setStage("ready");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export-Fehler");
      setStage("ready");
    }
  }

  function handleScrapeToggle(checked: boolean) {
    setScrapeEnabled(checked);
    if (checked && products.length > 0) {
      void loadMarketPrices(products);
    } else if (!checked) {
      scrapeAbortRef.current?.abort();
      setMarketPrices({});
      setScrapingStatus("");
      setScrapingProgress(null);
    }
  }

  function handleReset() {
    scrapeAbortRef.current?.abort();
    setStage("empty");
    setParseResult(null);
    setProducts([]);
    setEdits({});
    setSupplierName("");
    setError("");
    setMarketPrices({});
    setScrapingStatus("");
    setScrapingProgress(null);
    setScrapeEnabled(false);
    if (inputRef.current) inputRef.current.value = "";
  }

  function setEdit(rowId: number, field: keyof RowEdit, value: number | null) {
    setEdits((prev) => ({
      ...prev,
      [rowId]: {
        ordered_qty: prev[rowId]?.ordered_qty ?? null,
        vk_manual: prev[rowId]?.vk_manual ?? null,
        margin_pct: prev[rowId]?.margin_pct ?? margin,
        [field]: value,
      },
    }));
  }

  const isLoading = stage === "parsing" || stage === "extracting" || stage === "exporting";
  const hasFile = parseResult !== null;

  const filteredProducts = searchQuery.trim()
    ? products.filter((p) => {
        const q = searchQuery.toLowerCase();
        return (
          p.product_name?.toLowerCase().includes(q) ||
          p.sku?.toLowerCase().includes(q) ||
          p.ean?.toLowerCase().includes(q) ||
          p.color?.toLowerCase().includes(q) ||
          p.size?.toLowerCase().includes(q) ||
          p.category?.toLowerCase().includes(q)
        );
      })
    : products;

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <main className="sales-app">
      <header className="site-header">
        <div className="brand">
          <img src="/logo.png" alt="AMP Sport" className="brand-logo" />
          <span className="brand-divider" />
          <span className="brand-sub">Offerten Converter</span>
        </div>
      </header>

      {/* ── Hero (nur ohne Datei) ────────────────────────────────────────── */}

      {/* ── 3 Karten (immer sichtbar) ────────────────────────────────────── */}
      <section className="top-grid">

        {/* 1. Import */}
        <div
          className={hasFile ? "card import-card has-file" : "card import-card"}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); void handleFile(e.dataTransfer.files[0]); }}
        >
          <input accept=".xlsx,.xls,.csv" onChange={(e) => void handleFile(e.target.files?.[0])} ref={inputRef} type="file" />
          <div className="drop-art">
            <Icon name={isLoading ? "loader" : hasFile ? "check" : "upload"} size={36} />
          </div>
          <span className="drop-label">
            {stage === "parsing" ? "Wird gelesen …" : stage === "extracting" ? "Claude läuft …" : hasFile ? "Geladen" : "Import"}
          </span>
          <strong className="import-filename">{parseResult?.filename ?? "Excel oder CSV"}</strong>
          {hasFile && (
            <p className="import-meta">{parseResult!.row_count} Zeilen · {parseResult!.column_count} Spalten</p>
          )}
          <button disabled={isLoading} onClick={() => inputRef.current?.click()} type="button">
            {hasFile ? "Datei ersetzen" : "Datei hochladen"}
          </button>
          {hasFile && (
            <button className="reset-button" onClick={handleReset} type="button">Neue Offerte</button>
          )}
        </div>

        {/* 2. Datei Info */}
        <div className="card info-card">
          <p className="card-label">Datei Info</p>
          <div className="stat-grid">
            <div><span>Positionen</span><strong>{products.length > 0 ? products.length : parseResult ? parseResult.row_count : "—"}</strong></div>
            <div><span>Extraktion</span><strong>{parseResult ? (parseResult.extraction_mode === "local" ? "Lokal" : parseResult.extraction_mode === "cache" ? "Cache" : products.length > 0 ? "Claude ✓" : "Claude ausstehend") : "—"}</strong></div>
            <div><span>Kosten</span><strong>{parseResult == null ? "—" : parseResult.api_cost_estimate_chf != null ? `CHF ${parseResult.api_cost_estimate_chf.toFixed(3)}` : "Keine"}</strong></div>
          </div>
          {error && <p className="parse-error">{error}</p>}
          {needsAiExtraction && (
            <button className="extract-button" disabled={isLoading} onClick={() => void handleExtract()} type="button">
              Mit Claude extrahieren
            </button>
          )}
          {parseResult?.extraction_mode === "cache" && !isLoading && (
            <button className="reparse-button" onClick={() => void handleReparse()} type="button">
              Cache ignorieren & neu laden
            </button>
          )}
        </div>

        {/* 3. Marktpreise */}
        <div className="card market-card">
          <p className="card-label">Marktpreise</p>
          {hasFile && products.length > 0 ? (() => {
            const eanCount = products.filter(p => p.ean?.trim()).length;
            const secs = Math.ceil((eanCount / 3) * 3.8);
            const timeStr = secs >= 60 ? `ca. ${Math.round(secs / 60)} min` : `ca. ${secs} s`;
            return (
              <>
                <div className="market-stats">
                  <div className="market-stat">
                    <strong>{eanCount}</strong>
                    <span>EANs gefunden</span>
                  </div>
                  <div className="market-stat-divider" />
                  <div className="market-stat">
                    <strong>{timeStr}</strong>
                    <span>geschätzte Dauer</span>
                  </div>
                  <div className="market-stat-divider" />
                  <div className="market-stat">
                    <strong>{Object.keys(marketPrices).length > 0 ? Object.keys(marketPrices).length : "—"}</strong>
                    <span>Preise gefunden</span>
                  </div>
                </div>

                <p className="market-desc">Aktuelle Marktpreise von Toppreise.ch abrufen und als Grundlage für die VK-Kalkulation verwenden.</p>

                {scrapingProgress !== null && (
                  <div className="market-progress">
                    <div className="market-progress-bar" style={{ width: `${Math.round((scrapingProgress.done / scrapingProgress.total) * 100)}%` }} />
                    <span>{scrapingProgress.done} / {scrapingProgress.total}</span>
                  </div>
                )}
                {scrapingStatus && scrapingProgress === null && (
                  <p className="market-status">{scrapingStatus}</p>
                )}

                <button
                  className={scrapeEnabled ? "market-btn market-btn--stop" : "market-btn market-btn--start"}
                  onClick={() => handleScrapeToggle(!scrapeEnabled)}
                  type="button"
                  disabled={eanCount === 0}
                >
                  {scrapeEnabled ? "Suche stoppen" : "Marktpreise suchen"}
                </button>
              </>
            );
          })() : (
            <p className="actions-empty">Datei laden um Marktpreise zu suchen</p>
          )}
        </div>
      </section>

      {/* ── Vorschau + Einstellungen (nur mit Datei) ─────────────────────── */}
      {hasFile && (
        <section className="bottom-grid">

          {/* Vorschau – wide */}
          <div className="table-card">
            <div className="table-heading">
              <div>
                <span>Vorschau</span>
                <h2>
                  Erkannte Artikel
                  {products.length > 0 && <span className="heading-count"> — {filteredProducts.length}{searchQuery ? ` von ${products.length}` : ""} Positionen</span>}
                </h2>
              </div>
            </div>
            {products.length > 0 && (
              <div className="table-filter-bar">
                <span className="filter-label">Filtern</span>
                <input className="search-input" placeholder="Bezeichnung, SKU, EAN, Farbe, Grösse …" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} type="search" />
                {searchQuery && <button className="filter-clear" onClick={() => setSearchQuery("")} type="button">✕ löschen</button>}
              </div>
            )}
            {products.length > 0 ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>SKU</th><th>EAN</th><th>Bezeichnung</th><th>Grösse</th><th>Farbe</th>
                      <th>Verfügbar</th><th>EK/Stk</th><th>Marktpreis</th><th>VK/Stk (ca.)</th>
                      <th>Marge %</th><th>Menge</th><th>VK Total</th><th>VK manuell</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredProducts.map((row) => {
                      const edit = edits[row.row_id];
                      const rowMargin = (edit?.margin_pct ?? margin) / 100;
                      const mp = row.ean ? marketPrices[row.ean] : undefined;
                      const vkFromMarket = mp != null ? mp * (1 - marketDiscount / 100) : null;
                      const vkFromMargin = row.unit_price != null && rowMargin < 1 ? row.unit_price / (1 - rowMargin) : null;
                      const vkCalc = edit?.vk_manual != null ? edit.vk_manual : pricingMode === "market" ? (vkFromMarket ?? vkFromMargin) : vkFromMargin;
                      const vkIsMarketFallback = pricingMode === "market" && mp == null && vkCalc != null;
                      const currency = row.currency ?? "";
                      return (
                        <tr key={row.row_id}>
                          <td>{row.sku ?? "-"}</td>
                          <td style={{ fontFamily: "monospace", fontSize: 12 }}>{row.ean ?? "-"}</td>
                          <td>{row.product_name ?? "-"}</td>
                          <td>{row.size ?? "-"}</td>
                          <td>{row.color ?? "-"}</td>
                          <td style={{ textAlign: "right" }}>{row.available_qty ?? "-"}</td>
                          <td style={{ textAlign: "right" }}>{row.unit_price != null ? `${row.unit_price.toFixed(2)} ${currency}` : "-"}</td>
                          <td style={{ textAlign: "right" }}>{mp != null ? `CHF ${mp.toFixed(2)}` : "-"}</td>
                          <td style={{ textAlign: "right", fontWeight: 700, color: vkIsMarketFallback ? "var(--amp-muted)" : "var(--amp-navy)", fontStyle: vkIsMarketFallback ? "italic" : "normal" }}>
                            {vkCalc != null ? `${vkCalc.toFixed(2)} ${currency}${vkIsMarketFallback ? " *" : ""}` : "-"}
                          </td>
                          <td><input className="qty-input" max={99} min={0} step={0.5} type="number" onChange={(e) => setEdit(row.row_id, "margin_pct", Number(e.target.value))} value={edit?.margin_pct ?? margin} /></td>
                          <td><input className="qty-input" min={0} type="number" placeholder="0" onChange={(e) => setEdit(row.row_id, "ordered_qty", e.target.value ? Number(e.target.value) : null)} value={edit?.ordered_qty ?? ""} /></td>
                          <td style={{ textAlign: "right", fontWeight: 700, color: "var(--amp-navy)" }}>
                            {vkCalc != null && edit?.ordered_qty != null && edit.ordered_qty > 0 ? `${(vkCalc * edit.ordered_qty).toFixed(2)} ${currency}` : "-"}
                          </td>
                          <td><input className="qty-input" min={0} step={0.01} type="number" placeholder="auto" onChange={(e) => setEdit(row.row_id, "vk_manual", e.target.value ? Number(e.target.value) : null)} value={edit?.vk_manual ?? ""} /></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="table-empty">
                <Icon name="box" size={32} />
                <p>{searchQuery ? `Keine Treffer für «${searchQuery}»` : "Noch keine Artikel extrahiert."}</p>
              </div>
            )}
          </div>

          {/* Einstellungen – narrow */}
          <aside className="card settings-card">
            <p className="card-label">Offerte</p>
            <label className="settings-field">
              <span>Marke</span>
              <input onChange={(e) => setSupplierName(e.target.value)} placeholder="Lieferantenname" value={supplierName} />
            </label>
            <label className="settings-field">
              <span>Marge %</span>
              <input max={99} min={0} step={0.5} type="number" onChange={(e) => setMargin(Number(e.target.value))} value={margin} />
            </label>
            <label className="settings-field">
              <span>Währung</span>
              <select onChange={(e) => setTargetCurrency(e.target.value)} value={targetCurrency}>
                <option>CHF</option><option>EUR</option><option>USD</option>
              </select>
            </label>
            <div className="settings-field">
              <span>Preisberechnung</span>
              <div className="mode-toggle">
                <button className={pricingMode === "margin" ? "mode-btn active" : "mode-btn"} onClick={() => setPricingMode("margin")} type="button">EK + Marge</button>
                <button className={pricingMode === "market" ? "mode-btn active" : "mode-btn"} onClick={() => setPricingMode("market")} type="button">Marktpreis</button>
              </div>
            </div>
            {pricingMode === "market" && (
              <label className="settings-field">
                <span>Abzug vom Marktpreis</span>
                <input max={99} min={0} step={0.5} type="number" onChange={(e) => setMarketDiscount(Number(e.target.value))} value={marketDiscount} />
              </label>
            )}
          </aside>
        </section>
      )}
      {/* ── Floating export button ───────────────────────────────────────── */}
      {hasFile && products.length > 0 && (
        <button
          className={canExport && !isLoading ? "fab-export" : "fab-export fab-export--disabled"}
          disabled={!canExport || isLoading}
          onClick={() => void handleExport()}
          type="button"
        >
          <span className="fab-export-icon">
            <Icon name={stage === "exporting" ? "loader" : "download"} size={22} />
          </span>
          <span className="fab-export-text">
            <strong>{stage === "exporting" ? "Wird erstellt …" : "Offerte als Excel laden"}</strong>
            <small>{canExport ? `${filteredProducts.length} Artikel · ${supplierName}` : "Marke eintragen um fortzufahren"}</small>
          </span>
        </button>
      )}
    </main>
  );
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

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
  if (!cleaned) return "";
  return cleaned
    .split(" ")
    .filter(Boolean)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase())
    .join(" ");
}
