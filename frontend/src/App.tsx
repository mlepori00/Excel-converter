import { useRef, useState } from "react";

import { ExportFab } from "./components/ExportFab";
import { ImportCard } from "./components/ImportCard";
import { InfoCard } from "./components/InfoCard";
import { MarketCard } from "./components/MarketCard";
import { OverviewScreen } from "./components/OverviewScreen";
import { ProductTable } from "./components/ProductTable";
import { SettingsCard } from "./components/SettingsCard";
import {
  apiExport,
  apiExtract,
  apiParse,
  downloadBlob,
  inferSupplierName,
  API,
} from "./api";
import type { ExportSummary, ParseResult, ProductRow, RowEdit, Stage } from "./types";

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
  const [exportSummary, setExportSummary] = useState<ExportSummary | null>(null);

  const needsAiExtraction =
    parseResult !== null && parseResult.extraction_mode === "none" && products.length === 0;

  const hasFile = parseResult !== null;
  const isLoading = stage === "parsing" || stage === "extracting" || stage === "exporting";
  const canExport = stage === "ready" && supplierName.trim() !== "" && products.length > 0;

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

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  async function loadMarketPrices(rows: ProductRow[]) {
    const eans = rows.map((r) => r.ean?.trim() ?? "").filter((e) => e.length > 0);
    if (eans.length === 0) return;

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
      if (controller.signal.aborted) return;
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
        setStage("parsed");
      }
      if (!supplierName.trim()) setSupplierName(inferSupplierName(file.name));
      if (result.detected_currency) setTargetCurrency(result.detected_currency);
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
      const filename = `Offerte_${supplierName.trim().replace(/\s+/g, "_")}_${today}.xlsx`;
      downloadBlob(blob, filename);
      setExportSummary({
        supplierName: supplierName.trim(),
        articleCount: filteredProducts.length,
        currency: targetCurrency,
        filename,
      });
      setStage("exported");
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
    setExportSummary(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  function handleBackToDraft() {
    setStage("ready");
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

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <main className="sales-app">
      <header className="site-header">
        <div className="brand">
          <img src="/logo.png" alt="AMP Sport" className="brand-logo" />
          <span className="brand-divider" />
          <span className="brand-sub">Offerten Converter</span>
        </div>
      </header>

      {stage === "exported" && exportSummary ? (
        <OverviewScreen
          summary={exportSummary}
          onNewOffer={handleReset}
          onBack={handleBackToDraft}
        />
      ) : (
        <>
          <section className="top-grid">
            <ImportCard
                hasFile={hasFile}
                inputRef={inputRef}
                isLoading={isLoading}
                onFile={(f) => void handleFile(f)}
                onReset={handleReset}
                parseResult={parseResult}
                stage={stage}
            />
            <InfoCard
              error={error}
              isLoading={isLoading}
              needsAiExtraction={needsAiExtraction}
              onExtract={() => void handleExtract()}
              onReparse={() => void handleReparse()}
              parseResult={parseResult}
              products={products}
            />
            <MarketCard
              hasFile={hasFile}
              marketPrices={marketPrices}
              onScrapeToggle={handleScrapeToggle}
              products={products}
              scrapeEnabled={scrapeEnabled}
              scrapingProgress={scrapingProgress}
              scrapingStatus={scrapingStatus}
            />
          </section>

          {hasFile && (
            <section className="bottom-grid">
              <ProductTable
                edits={edits}
                filteredProducts={filteredProducts}
                margin={margin}
                marketDiscount={marketDiscount}
                marketPrices={marketPrices}
                onEdit={setEdit}
                onSearchChange={setSearchQuery}
                pricingMode={pricingMode}
                products={products}
                searchQuery={searchQuery}
              />
              <SettingsCard
                margin={margin}
                marketDiscount={marketDiscount}
                onCurrencyChange={setTargetCurrency}
                onMarginChange={setMargin}
                onMarketDiscountChange={setMarketDiscount}
                onPricingModeChange={setPricingMode}
                onSupplierNameChange={setSupplierName}
                pricingMode={pricingMode}
                supplierName={supplierName}
                targetCurrency={targetCurrency}
              />
            </section>
          )}

          {hasFile && products.length > 0 && (
            <ExportFab
              canExport={canExport}
              filteredProducts={filteredProducts}
              isLoading={isLoading}
              onExport={() => void handleExport()}
              stage={stage}
              supplierName={supplierName}
            />
          )}
        </>
      )}
    </main>
  );
}
