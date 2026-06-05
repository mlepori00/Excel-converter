import type { MapColumnsResult, ParseResult } from "../types";

type Props = {
  parseResult: ParseResult | null;
  isLoading: boolean;
  isMappingColumns: boolean;
  mappingError: string;
  columnMappingResult: MapColumnsResult | null;
  onMapColumns: () => void;
};

function fmtChf(v: number): string {
  if (v < 0.01) return v.toFixed(4);
  return v.toFixed(2);
}

export function HeaderCard({
  parseResult,
  isLoading,
  isMappingColumns,
  mappingError,
  columnMappingResult,
  onMapColumns,
}: Props) {
  const isBusy = isLoading || isMappingColumns;
  const r = columnMappingResult;

  return (
    <div className="card header-card">
      <p className="card-label">Header identifizieren</p>

      {r && (
        <div className="hc-breakdown">
          <div className="hc-summary">
            <strong>{r.columns_mapped}</strong>
            <span>von {r.columns_total} Spalten zugewiesen</span>
          </div>

          <div className="hc-map">
            {Object.entries(r.mapped_fields).map(([canonical, original]) => (
              <div className="hc-map-row" key={canonical}>
                <span className="hc-map-src" title={original}>{original}</span>
                <span className="hc-map-arrow">→</span>
                <span className="hc-map-dst">{canonical}</span>
              </div>
            ))}
          </div>

          {r.unmapped_columns.length > 0 && (
            <div className="hc-unmapped">
              <p className="hc-unmapped-label">{r.unmapped_columns.length} nicht zugewiesen</p>
              <p className="hc-unmapped-list">{r.unmapped_columns.join(" · ")}</p>
            </div>
          )}
        </div>
      )}

      {mappingError && <p className="parse-error">{mappingError}</p>}

      {parseResult && (
        <div className="action-row">
          <button
            className="action-btn"
            disabled={isBusy}
            onClick={onMapColumns}
            type="button"
          >
            {isMappingColumns ? "Analysiert …" : r ? "Erneut analysieren" : "Header analysieren"}
          </button>
          {parseResult.map_columns_cost_estimate_chf != null && (
            <span className="action-cost">
              ~ CHF {fmtChf(parseResult.map_columns_cost_estimate_chf)}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
