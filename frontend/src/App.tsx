import { useEffect, useRef, useState } from "react";

import { ArchiveView } from "./components/ArchiveView";
import { ChangePasswordScreen } from "./components/ChangePasswordScreen";
import { ColumnMappingModal } from "./components/ColumnMappingModal";
import { ExportFab } from "./components/ExportFab";
import { FlowSteps } from "./components/FlowSteps";
import { HeaderCard } from "./components/HeaderCard";
import { ImportCard } from "./components/ImportCard";
import { InfoCard } from "./components/InfoCard";
import { MarketCard } from "./components/MarketCard";
import { OverviewScreen } from "./components/OverviewScreen";
import { ProductTable } from "./components/ProductTable";
import { SettingsCard } from "./components/SettingsCard";
import {
  apiBrandSupplierIndex,
  apiColumnOptions,
  apiExport,
  apiExtract,
  apiMapColumns,
  apiParse,
  apiRates,
  apiRemapColumns,
  downloadBlob,
  handleUnauthorized,
  inferSupplierName,
  API,
  _authHeader,
} from "./api";
import type { ResolveStatus } from "./components/Combobox";
import type {
  AuthUser,
  ColumnOptionsResult,
  ExportSummary,
  MapColumnsResult,
  ParseResult,
  ProductRow,
  RowEdit,
  Stage,
} from "./types";

type AppProps = {
  user: AuthUser;
  onLogout: () => void;
};

// The margin a user sets is remembered across sessions (per browser).
const MARGIN_STORAGE_KEY = "oc_default_margin";
const FALLBACK_MARGIN = 20;

function loadStoredMargin(): number {
  if (typeof localStorage === "undefined") return FALLBACK_MARGIN;
  const parsed = Number(localStorage.getItem(MARGIN_STORAGE_KEY));
  return Number.isFinite(parsed) && parsed > 0 && parsed <= 99 ? parsed : FALLBACK_MARGIN;
}

export default function App({ user, onLogout }: AppProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const scrapeAbortRef = useRef<AbortController | null>(null);
  const fileRef = useRef<File | null>(null);

  const [stage, setStage] = useState<Stage>("empty");
  const [error, setError] = useState("");
  const [showChangePw, setShowChangePw] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const [view, setView] = useState<"create" | "archive">("create");

  const [parseResult, setParseResult] = useState<ParseResult | null>(null);
  const [products, setProducts] = useState<ProductRow[]>([]);
  const [edits, setEdits] = useState<Record<number, RowEdit>>({});

  const [supplierName, setSupplierName] = useState("");
  const [marke, setMarke] = useState("");
  const [brands, setBrands] = useState<string[]>([]);
  const [allSuppliers, setAllSuppliers] = useState<string[]>([]);
  const [suppliersByBrand, setSuppliersByBrand] = useState<Record<string, string[]>>({});
  const [markeStatus, setMarkeStatus] = useState<ResolveStatus>("empty");
  const [supplierStatus, setSupplierStatus] = useState<ResolveStatus>("empty");
  const [margin, setMargin] = useState(loadStoredMargin);
  const [targetCurrency, setTargetCurrency] = useState("CHF");
  // Reference exchange rates (live ECB, "1 CHF = X foreign"); fallback is static.
  const [liveRates, setLiveRates] = useState<Record<string, number>>({});
  const [rateDate, setRateDate] = useState<string | null>(null);
  const [rateLive, setRateLive] = useState(true);
  // Per-offer manual overrides: "1 <source> = <value> <targetCurrency>". Not persisted.
  const [rateOverrides, setRateOverrides] = useState<Record<string, number>>({});
  const [marketPrices, setMarketPrices] = useState<Record<string, number>>({});
  const [scrapingStatus, setScrapingStatus] = useState("");
  const [scrapingProgress, setScrapingProgress] = useState<{ done: number; total: number } | null>(null);

  const [pricingMode, setPricingMode] = useState<"margin" | "market">("margin");
  const [marketDiscount, setMarketDiscount] = useState(20);
  const [isSampling, setIsSampling] = useState(false);
  const [sampleResult, setSampleResult] = useState<{
    hit: number;
    total: number;
    eans: Array<{ ean: string; found: boolean }>;
  } | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [exportSummary, setExportSummary] = useState<ExportSummary | null>(null);
  const [isMappingColumns, setIsMappingColumns] = useState(false);
  const [columnMappingResult, setColumnMappingResult] = useState<MapColumnsResult | null>(null);
  const [mappingError, setMappingError] = useState("");

  // Manual column-mapping modal (no AI).
  const [showMapping, setShowMapping] = useState(false);
  const [mappingOptions, setMappingOptions] = useState<ColumnOptionsResult | null>(null);
  const [mappingOptionsLoading, setMappingOptionsLoading] = useState(false);
  const [isRemapping, setIsRemapping] = useState(false);

  const needsAiExtraction =
    parseResult !== null && parseResult.extraction_mode === "none" && products.length === 0;

  const hasFile = parseResult !== null;
  const isLoading = stage === "parsing" || stage === "extracting" || stage === "exporting";
  const canExport =
    stage === "ready" &&
    supplierName.trim() !== "" &&
    marke.trim() !== "" &&
    markeStatus !== "unconfirmed" &&
    supplierStatus !== "unconfirmed" &&
    products.length > 0;

  // Guided-flow step: first action the user still needs to take.
  const offerComplete =
    marke.trim() !== "" &&
    supplierName.trim() !== "" &&
    markeStatus !== "unconfirmed" &&
    supplierStatus !== "unconfirmed";
  const currentStep = !hasFile ? 1 : products.length === 0 ? 2 : !offerComplete ? 3 : 4;

  function handleMarginChange(value: number) {
    setMargin(value);
    if (typeof localStorage !== "undefined" && Number.isFinite(value) && value > 0 && value <= 99) {
      localStorage.setItem(MARGIN_STORAGE_KEY, String(value));
    }
  }

  // Load the brand/supplier suggestion index for the create flow.
  function loadBrandSupplierIndex() {
    apiBrandSupplierIndex()
      .then((idx) => {
        setBrands(idx.brands);
        setAllSuppliers(idx.allSuppliers);
        setSuppliersByBrand(idx.suppliersByBrand);
      })
      .catch(() => undefined);
  }
  useEffect(loadBrandSupplierIndex, []);

  // Load reference exchange rates once (live ECB, static fallback handled server-side).
  useEffect(() => {
    apiRates()
      .then((r) => {
        setLiveRates(r.rates);
        setRateDate(r.date);
        setRateLive(r.live);
      })
      .catch(() => setRateLive(false));
  }, []);

  // Close the user menu on outside click or Escape.
  useEffect(() => {
    if (!menuOpen) return;
    function onClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

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

  // Distinct source currencies in the offer that differ from the target currency.
  // A blank row currency is treated as CHF (matches the backend pricing default).
  const targetUpper = targetCurrency.toUpperCase();
  const foreignCurrencies = Array.from(
    new Set(products.map((p) => (p.currency || "CHF").toUpperCase()))
  ).filter((c) => c !== targetUpper);

  // Live "1 <cur> = X <target>" reference, derived from the CHF-based ECB table.
  function liveMultiplier(cur: string): number | null {
    const s = liveRates[cur.toUpperCase()];
    const t = liveRates[targetUpper];
    if (!s || !t) return null;
    return t / s;
  }

  // Rows for the settings UI: each foreign currency with its live + effective value.
  const rateRows = foreignCurrencies.map((cur) => {
    const live = liveMultiplier(cur);
    const override = rateOverrides[cur];
    return { currency: cur, live, value: override ?? live };
  });

  // Build the CHF-based rates dict for export. Start from the live table, then
  // translate each manual "1 cur = v target" override into the CHF-based slot:
  //   convert(cur→target) = rates[target]/rates[cur]  ⇒  rates[cur] = rates[target]/v
  function buildExportRates(): Record<string, number> {
    const out: Record<string, number> = { ...liveRates };
    const tgtRate = liveRates[targetUpper] ?? 1.0;
    for (const [cur, v] of Object.entries(rateOverrides)) {
      const key = cur.toUpperCase();
      // Never override the target currency's own slot (it must stay self-consistent).
      if (key === targetUpper || !v || v <= 0) continue;
      out[key] = tgtRate / v;
    }
    return out;
  }

  function handleRateChange(currency: string, value: number) {
    setRateOverrides((prev) => ({ ...prev, [currency.toUpperCase()]: value }));
  }

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
        headers: { "Content-Type": "application/json", ..._authHeader() },
        body: JSON.stringify({ eans }),
        signal: controller.signal,
      });
    } catch {
      if (controller.signal.aborted) return;
      setScrapingProgress(null);
      setScrapingStatus("Marktpreis-Abfrage fehlgeschlagen");
      return;
    }

    if (handleUnauthorized(resp.status)) return;
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
    setRateOverrides({});

    try {
      const result = await apiParse(file);
      setParseResult(result);
      if (result.products.length > 0) {
        setProducts(result.products);
        setStage("ready");
      } else {
        setStage("parsed");
      }
      if (!supplierName.trim()) setSupplierName(inferSupplierName(file.name));
      if (result.detected_currency) setTargetCurrency(result.detected_currency);

      // When local extraction found nothing, immediately offer manual column mapping.
      if (result.extraction_mode === "none" && result.products.length === 0) {
        setShowMapping(true);
        setMappingOptions(null);
        setMappingError("");
        setMappingOptionsLoading(true);
        try {
          const options = await apiColumnOptions(result.file_id, {});
          setMappingOptions(options);
        } catch (e) {
          setMappingError(e instanceof Error ? e.message : "Spalten konnten nicht geladen werden");
        } finally {
          setMappingOptionsLoading(false);
        }
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
      } else {
        setStage("parsed");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Fehler beim Neu-Laden");
      setStage("ready");
    }
  }

  async function handleMapColumns() {
    if (!parseResult) return;
    setIsMappingColumns(true);
    setMappingError("");
    try {
      const result = await apiMapColumns(parseResult.file_id);
      setColumnMappingResult(result);
      if (result.products.length > 0) {
        setProducts(result.products);
        setStage("ready");
      }
    } catch (e) {
      setMappingError(e instanceof Error ? e.message : "Fehler bei Header-Analyse");
    } finally {
      setIsMappingColumns(false);
    }
  }

  async function handleOpenManualMapping() {
    if (!parseResult) return;
    setShowMapping(true);
    setMappingOptions(null);
    setMappingError("");
    setMappingOptionsLoading(true);
    try {
      const options = await apiColumnOptions(
        parseResult.file_id,
        columnMappingResult?.mapped_fields ?? {},
      );
      setMappingOptions(options);
    } catch (e) {
      setMappingError(e instanceof Error ? e.message : "Spalten konnten nicht geladen werden");
    } finally {
      setMappingOptionsLoading(false);
    }
  }

  async function handleApplyManualMapping(mapping: Record<string, string>) {
    if (!parseResult) return;
    setIsRemapping(true);
    setMappingError("");
    try {
      const result = await apiRemapColumns(
        parseResult.file_id,
        mapping,
        columnMappingResult?.mapped_fields ?? {},
      );
      setColumnMappingResult(result);
      setEdits({});
      setProducts(result.products);
      setStage(result.products.length > 0 ? "ready" : "parsed");
      setShowMapping(false);
    } catch (e) {
      setMappingError(e instanceof Error ? e.message : "Zuordnung fehlgeschlagen");
    } finally {
      setIsRemapping(false);
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

      const { blob, offerId } = await apiExport(
        parseResult.file_id,
        supplierName.trim(),
        targetCurrency,
        margin,
        filteredProducts,
        effectiveEdits,
        marketPrices,
        user.name,
        marke.trim(),
        buildExportRates()
      );
      const today = new Date().toISOString().slice(0, 10).replace(/-/g, "");
      const filename = `Offerte_${supplierName.trim().replace(/\s+/g, "_")}_${today}.xlsx`;
      downloadBlob(blob, filename);
      setExportSummary({
        supplierName: supplierName.trim(),
        marke: marke.trim(),
        articleCount: filteredProducts.length,
        currency: targetCurrency,
        filename,
        archived: offerId !== null,
      });
      // Refresh suggestions so a newly used brand/supplier appears next time.
      loadBrandSupplierIndex();
      setStage("exported");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export-Fehler");
      setStage("ready");
    }
  }

  async function handleSample() {
    const allEans = [
      ...new Set(products.map((p) => p.ean?.trim() ?? "").filter((e) => e.length > 0)),
    ];
    if (allEans.length === 0) return;

    const shuffled = [...allEans].sort(() => Math.random() - 0.5);
    const sampleEans = shuffled.slice(0, Math.min(10, allEans.length));

    scrapeAbortRef.current?.abort();
    const controller = new AbortController();
    scrapeAbortRef.current = controller;

    setIsSampling(true);
    setSampleResult(null);
    setMarketPrices({});
    setScrapingStatus("");
    setScrapingProgress({ done: 0, total: sampleEans.length });

    let resp: Response;
    try {
      resp = await fetch(`${API}/api/offer/market-prices/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ..._authHeader() },
        body: JSON.stringify({ eans: sampleEans }),
        signal: controller.signal,
      });
    } catch {
      if (!controller.signal.aborted) setScrapingProgress(null);
      setIsSampling(false);
      return;
    }

    if (handleUnauthorized(resp.status)) {
      setIsSampling(false);
      return;
    }
    if (!resp.ok || !resp.body) {
      setScrapingProgress(null);
      setIsSampling(false);
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
              setScrapingProgress(null);
              setSampleResult({
                hit: Object.keys(prices).length,
                total: sampleEans.length,
                eans: sampleEans.map((e) => ({ ean: e, found: e in prices })),
              });
              setIsSampling(false);
            }
          } catch {
            // malformed SSE line – skip
          }
        }
      }
    } catch {
      if (!controller.signal.aborted) setScrapingProgress(null);
      setIsSampling(false);
    }
  }

  function handleScrapeAll() {
    void loadMarketPrices(products);
  }

  function handleStopScrape() {
    scrapeAbortRef.current?.abort();
    setIsSampling(false);
    setScrapingProgress(null);
    setScrapingStatus("Suche abgebrochen");
  }

  function handleReset() {
    scrapeAbortRef.current?.abort();
    setStage("empty");
    setParseResult(null);
    setProducts([]);
    setEdits({});
    setSupplierName("");
    setMarke("");
    setError("");
    setMarketPrices({});
    setScrapingStatus("");
    setScrapingProgress(null);
    setIsSampling(false);
    setSampleResult(null);
    setExportSummary(null);
    setColumnMappingResult(null);
    setMappingError("");
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
        <nav className="app-nav">
          <button
            className={view === "create" ? "nav-btn active" : "nav-btn"}
            onClick={() => setView("create")}
            type="button"
          >
            Neue Offerte
          </button>
          <button
            className={view === "archive" ? "nav-btn active" : "nav-btn"}
            onClick={() => setView("archive")}
            type="button"
          >
            Archiv
          </button>
        </nav>
        <div className="user-menu" ref={menuRef}>
          <button
            type="button"
            className="user-menu__trigger"
            onClick={() => setMenuOpen((o) => !o)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
          >
            <span className="user-name">{user.name}</span>
            <span className={menuOpen ? "user-menu__caret open" : "user-menu__caret"}>▾</span>
          </button>
          {menuOpen && (
            <div className="user-menu__dropdown" role="menu">
              <button
                type="button"
                className="user-menu__item"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false);
                  setShowChangePw(true);
                }}
              >
                Passwort ändern
              </button>
              <button
                type="button"
                className="user-menu__item"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false);
                  onLogout();
                }}
              >
                Abmelden
              </button>
            </div>
          )}
        </div>
      </header>

      {showChangePw && (
        <ChangePasswordScreen
          forced={false}
          onDone={() => setShowChangePw(false)}
          onCancel={() => setShowChangePw(false)}
        />
      )}

      <ColumnMappingModal
        error={mappingError}
        isApplying={isRemapping}
        isLoading={mappingOptionsLoading}
        onApply={(m) => void handleApplyManualMapping(m)}
        onClose={() => setShowMapping(false)}
        open={showMapping}
        options={mappingOptions}
      />

      {view === "archive" ? (
        <ArchiveView />
      ) : stage === "exported" && exportSummary ? (
        <OverviewScreen
          summary={exportSummary}
          onNewOffer={handleReset}
          onBack={handleBackToDraft}
        />
      ) : (
        <>
          <FlowSteps current={currentStep} />
          <section className={hasFile ? "work-top work-top--offer" : "work-top"}>
            <div className="setup-grid">
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
                columnMappingResult={columnMappingResult}
                error={error}
                isLoading={isLoading}
                isMappingColumns={isMappingColumns}
                mappingError={mappingError}
                needsAiExtraction={needsAiExtraction}
                onExtract={() => void handleExtract()}
                onForceExtract={() => void handleExtract()}
                onMapColumns={() => void handleMapColumns()}
                onReparse={() => void handleReparse()}
                parseResult={parseResult}
                products={products}
              />
              <HeaderCard
                columnMappingResult={columnMappingResult}
                isLoading={isLoading}
                isMappingColumns={isMappingColumns}
                mappingError={mappingError}
                onManualMap={() => void handleOpenManualMapping()}
                onMapColumns={() => void handleMapColumns()}
                parseResult={parseResult}
              />
              <MarketCard
                hasFile={hasFile}
                isSampling={isSampling}
                marketPrices={marketPrices}
                onSample={() => void handleSample()}
                onScrapeAll={handleScrapeAll}
                onStop={handleStopScrape}
                products={products}
                sampleResult={sampleResult}
                scrapingProgress={scrapingProgress}
                scrapingStatus={scrapingStatus}
              />
            </div>
            {hasFile && (
              <SettingsCard
                allSuppliers={allSuppliers}
                brands={brands}
                margin={margin}
                marke={marke}
                marketDiscount={marketDiscount}
                onCurrencyChange={setTargetCurrency}
                onMarginChange={handleMarginChange}
                onMarketDiscountChange={setMarketDiscount}
                onMarkeChange={setMarke}
                onMarkeStatusChange={setMarkeStatus}
                onPricingModeChange={setPricingMode}
                onRateChange={handleRateChange}
                onSupplierNameChange={setSupplierName}
                onSupplierStatusChange={setSupplierStatus}
                pricingMode={pricingMode}
                rateDate={rateDate}
                rateLive={rateLive}
                rateRows={rateRows}
                suppliersByBrand={suppliersByBrand}
                supplierName={supplierName}
                targetCurrency={targetCurrency}
              />
            )}
          </section>

          {hasFile && (
            <section className="table-section">
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
