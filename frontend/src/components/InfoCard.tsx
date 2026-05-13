import type { ParseResult, ProductRow } from "../types";

type Props = {
  parseResult: ParseResult | null;
  products: ProductRow[];
  isLoading: boolean;
  needsAiExtraction: boolean;
  error: string;
  onExtract: () => void;
  onReparse: () => void;
};

export function InfoCard({
  parseResult,
  products,
  isLoading,
  needsAiExtraction,
  error,
  onExtract,
  onReparse,
}: Props) {
  const extractionLabel = parseResult
    ? parseResult.extraction_mode === "local"
      ? "Lokal"
      : parseResult.extraction_mode === "cache"
      ? "Cache"
      : products.length > 0
      ? "Claude ✓"
      : "Claude ausstehend"
    : "—";

  return (
    <div className="card info-card">
      <p className="card-label">Datei Info</p>
      <div className="stat-grid">
        <div>
          <span>Positionen</span>
          <strong>
            {products.length > 0 ? products.length : parseResult ? parseResult.row_count : "—"}
          </strong>
        </div>
        <div>
          <span>Extraktion</span>
          <strong>{extractionLabel}</strong>
        </div>
        <div>
          <span>Kosten</span>
          <strong>
            {parseResult == null
              ? "—"
              : parseResult.api_cost_estimate_chf != null
              ? `CHF ${parseResult.api_cost_estimate_chf.toFixed(3)}`
              : "Keine"}
          </strong>
        </div>
      </div>
      {error && <p className="parse-error">{error}</p>}
      {needsAiExtraction && (
        <button
          className="extract-button"
          disabled={isLoading}
          onClick={onExtract}
          type="button"
        >
          Mit Claude extrahieren
        </button>
      )}
      {parseResult?.extraction_mode === "cache" && !isLoading && (
        <button className="reparse-button" onClick={onReparse} type="button">
          Cache ignorieren &amp; neu laden
        </button>
      )}
    </div>
  );
}
