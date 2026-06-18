import { useEffect, useState } from "react";

import type { ColumnOptionsResult } from "../types";

// German labels for the canonical fields the user can map.
const FIELD_LABELS: Record<string, string> = {
  sku: "Artikelnummer (SKU)",
  ean: "EAN / Barcode",
  product_name: "Produktname",
  size: "Grösse",
  color: "Farbe",
  category: "Kategorie",
  available_qty: "Verfügbar",
  ordered_qty: "Bestellmenge",
  unit_price: "Einkaufspreis",
  currency: "Währung",
  discount_pct: "Rabatt %",
};

type Props = {
  open: boolean;
  options: ColumnOptionsResult | null;
  isLoading: boolean;
  isApplying: boolean;
  error: string;
  onApply: (mapping: Record<string, string>) => void;
  onClose: () => void;
};

export function ColumnMappingModal({
  open,
  options,
  isLoading,
  isApplying,
  error,
  onApply,
  onClose,
}: Props) {
  const [mapping, setMapping] = useState<Record<string, string>>({});

  // Re-initialize the form whenever fresh options arrive.
  useEffect(() => {
    if (options) setMapping({ ...options.current_mapping });
  }, [options]);

  if (!open) return null;

  const columnNames = options?.columns.map((c) => c.name) ?? [];
  const samplesByName = new Map((options?.columns ?? []).map((c) => [c.name, c.samples]));

  function setField(field: string, value: string) {
    setMapping((prev) => ({ ...prev, [field]: value }));
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card mapping-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>Spalten manuell zuordnen</h2>
          <button aria-label="Schliessen" className="modal-close" onClick={onClose} type="button">
            ×
          </button>
        </div>
        <p className="modal-sub">
          Ordne jede Eigenschaft der passenden Spalte aus der Datei zu. Keine KI nötig.
        </p>

        {isLoading && <p className="modal-loading">Spalten werden geladen …</p>}
        {error && <p className="parse-error">{error}</p>}

        {!isLoading && options && (
          <div className="mapping-grid">
            {options.fields.map((field) => {
              const selected = mapping[field] ?? "";
              const samples = selected ? samplesByName.get(selected) ?? [] : [];
              return (
                <div className="mapping-field" key={field}>
                  <label>{FIELD_LABELS[field] ?? field}</label>
                  <select onChange={(e) => setField(field, e.target.value)} value={selected}>
                    <option value="">— nicht zugeordnet —</option>
                    {columnNames.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                  {samples.length > 0 && (
                    <small className="mapping-samples">z. B. {samples.join(" · ")}</small>
                  )}
                </div>
              );
            })}
          </div>
        )}

        <div className="modal-actions">
          <button className="action-btn" disabled={isApplying} onClick={onClose} type="button">
            Abbrechen
          </button>
          <button
            className="action-btn action-btn--primary"
            disabled={isApplying || isLoading || !options}
            onClick={() => onApply(mapping)}
            type="button"
          >
            {isApplying ? "Wird übernommen …" : "Übernehmen"}
          </button>
        </div>
      </div>
    </div>
  );
}
