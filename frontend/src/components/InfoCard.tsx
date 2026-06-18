import type { MapColumnsResult, ParseResult, ProductRow } from "../types";

type Props = {
  parseResult: ParseResult | null;
  products: ProductRow[];
  isLoading: boolean;
  isMappingColumns: boolean;
  needsAiExtraction: boolean;
  error: string;
  mappingError: string;
  columnMappingResult: MapColumnsResult | null;
  onExtract: () => void;
  onReparse: () => void;
  onForceExtract: () => void;
  onMapColumns: () => void;
};

function MappingPills({ result }: { result: MapColumnsResult }) {
  const entries = Object.entries(result.mapped_fields);
  const isWarn = result.columns_mapped < 3;
  return (
    <div className={`mapping-result ${isWarn ? "mapping-result--warn" : "mapping-result--ok"}`}>
      <span className="mapping-result__label">
        {result.columns_mapped === 0
          ? "Keine Felder erkannt – Dateistruktur prüfen"
          : `${result.columns_mapped}/${result.columns_total} Spalten erkannt`}
      </span>
      {entries.length > 0 && (
        <div className="mapping-pills">
          {entries.map(([canonical, original]) => (
            <span className="mapping-pill" key={canonical}>
              <span className="mapping-pill__orig">{original}</span>
              <span className="mapping-pill__arrow">→</span>
              <span className="mapping-pill__canon">{canonical}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function InfoCard({
  parseResult,
  products,
  isLoading,
  isMappingColumns,
  needsAiExtraction,
  error,
  mappingError,
  columnMappingResult,
  onExtract,
  onReparse,
  onForceExtract,
  onMapColumns,
}: Props) {
  const isBusy = isLoading || isMappingColumns;

  const extractionLabel = parseResult
    ? parseResult.extraction_mode === "local"
      ? "Lokal"
      : parseResult.extraction_mode === "cache"
      ? "Cache"
      : products.length > 0
      ? "Claude ✓"
      : "Ausstehend"
    : "—";

  // AI extraction is the backup path: prominent only when the local
  // heuristic found nothing; otherwise a quiet redo link suffices.
  const extractionSucceeded =
    parseResult?.extraction_mode === "local" || parseResult?.extraction_mode === "cache";
  const showCache = parseResult?.extraction_mode === "cache";

  return (
    <div className="card extraction-card">
      <p className="card-label">Datei &amp; Extraktion</p>

      <div className="stat-grid">
        <div>
          <span>Positionen</span>
          <strong>
            {products.length > 0
              ? products.length
              : parseResult
              ? parseResult.row_count
              : "—"}
          </strong>
        </div>
        <div>
          <span>Extraktion</span>
          <strong>{extractionLabel}</strong>
        </div>
      </div>

      {(error || mappingError) && <p className="parse-error">{error || mappingError}</p>}

      {parseResult && needsAiExtraction && (
        <>
          {parseResult.extraction_diagnostics && (
            <p className="extraction-diagnostics">{parseResult.extraction_diagnostics}</p>
          )}
          <div className="action-row">
            <button
              className="action-btn action-btn--primary"
              disabled={isBusy}
              onClick={onExtract}
              type="button"
            >
              {isLoading ? "Extrahiert …" : "Mit Claude extrahieren"}
            </button>
            {parseResult.api_cost_estimate_chf != null && (
              <span className="action-cost">
                ~ CHF {parseResult.api_cost_estimate_chf.toFixed(2)}
              </span>
            )}
          </div>
        </>
      )}

      {parseResult && extractionSucceeded && !needsAiExtraction && (
        <button
          className="reparse-button"
          disabled={isBusy}
          onClick={onForceExtract}
          type="button"
        >
          {isLoading
            ? "Extrahiert …"
            : `Mit KI neu extrahieren${
                parseResult.api_cost_estimate_chf != null
                  ? ` (~ CHF ${parseResult.api_cost_estimate_chf.toFixed(2)})`
                  : ""
              }`}
        </button>
      )}

      {showCache && !isBusy && (
        <button className="reparse-button" onClick={onReparse} type="button">
          Cache ignorieren &amp; neu laden
        </button>
      )}
    </div>
  );
}
