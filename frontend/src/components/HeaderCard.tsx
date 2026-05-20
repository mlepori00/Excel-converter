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

          <div className="hc-section">
            <p className="hc-section__title hc-section__title--ok">
              {r.columns_mapped}/{r.columns_total} Spalten erkannt
            </p>
            <div className="mapping-pills">
              {Object.entries(r.mapped_fields).map(([canonical, original]) => (
                <span className="mapping-pill" key={canonical}>
                  <span className="mapping-pill__orig">{original}</span>
                  <span className="mapping-pill__arrow">→</span>
                  <span className="mapping-pill__canon">{canonical}</span>
                </span>
              ))}
            </div>
          </div>

          {r.unmapped_columns.length > 0 && (
            <div className="hc-section">
              <p className="hc-section__title hc-section__title--neutral">
                {r.unmapped_columns.length}/{r.columns_total} nicht zugewiesen
              </p>
              <div className="unmapped-pills">
                {r.unmapped_columns.map((col) => (
                  <span className="unmapped-pill" key={col}>{col}</span>
                ))}
              </div>
            </div>
          )}

          <p className="hc-total">
            ✓&nbsp;{r.columns_total}/{r.columns_total} Spalten analysiert
          </p>
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
