import { Combobox } from "./Combobox";
import type { ResolveStatus } from "./Combobox";

export type RateRow = {
  /** Foreign source currency, e.g. "EUR". */
  currency: string;
  /** Live reference rate "1 currency = live target", or null if unavailable. */
  live: number | null;
  /** Currently effective value shown in the input (override, else live). */
  value: number | null;
};

type Props = {
  supplierName: string;
  marke: string;
  brands: string[];
  allSuppliers: string[];
  suppliersByBrand: Record<string, string[]>;
  margin: number;
  targetCurrency: string;
  pricingMode: "margin" | "market";
  marketDiscount: number;
  rateRows: RateRow[];
  rateDate: string | null;
  rateLive: boolean;
  onSupplierNameChange: (v: string) => void;
  onMarkeChange: (v: string) => void;
  onMarkeStatusChange: (s: ResolveStatus) => void;
  onSupplierStatusChange: (s: ResolveStatus) => void;
  onMarginChange: (v: number) => void;
  onCurrencyChange: (v: string) => void;
  onPricingModeChange: (v: "margin" | "market") => void;
  onMarketDiscountChange: (v: number) => void;
  onRateChange: (currency: string, value: number) => void;
};

export function SettingsCard({
  supplierName,
  marke,
  brands,
  allSuppliers,
  suppliersByBrand,
  margin,
  targetCurrency,
  pricingMode,
  marketDiscount,
  rateRows,
  rateDate,
  rateLive,
  onSupplierNameChange,
  onMarkeChange,
  onMarkeStatusChange,
  onSupplierStatusChange,
  onMarginChange,
  onCurrencyChange,
  onPricingModeChange,
  onMarketDiscountChange,
  onRateChange,
}: Props) {
  // Suppliers already used with the chosen brand are suggested first.
  const brandSuppliers = suppliersByBrand[marke.trim()] ?? [];

  return (
    <aside className="card settings-card">
      <p className="card-label">Offerte</p>

      <Combobox
        label="Marke"
        value={marke}
        onChange={onMarkeChange}
        onStatusChange={onMarkeStatusChange}
        options={brands}
        placeholder="z. B. Nike"
      />

      <Combobox
        label="Lieferant"
        value={supplierName}
        onChange={onSupplierNameChange}
        onStatusChange={onSupplierStatusChange}
        options={allSuppliers}
        priorityOptions={brandSuppliers}
        priorityLabel={marke.trim() ? `Lieferanten von ${marke.trim()}` : undefined}
        restLabel="Alle Lieferanten"
        placeholder="Lieferantenname"
      />

      <label className="settings-field">
        <span>Marge %</span>
        <input
          max={99}
          min={0}
          onChange={(e) => onMarginChange(Number(e.target.value))}
          step={0.5}
          type="number"
          value={margin}
        />
      </label>

      <label className="settings-field">
        <span>Währung</span>
        <select onChange={(e) => onCurrencyChange(e.target.value)} value={targetCurrency}>
          <option>CHF</option>
          <option>EUR</option>
          <option>USD</option>
        </select>
      </label>

      {rateRows.length > 0 && (
        <div className="settings-field rate-field">
          <span>Wechselkurs</span>
          {rateRows.map((r) => (
            <div className="rate-row" key={r.currency}>
              <div className="rate-input">
                <span className="rate-eq">1 {r.currency} =</span>
                <input
                  min={0}
                  onChange={(e) => onRateChange(r.currency, Number(e.target.value))}
                  step={0.0001}
                  type="number"
                  value={r.value ?? ""}
                />
                <span className="rate-eq">{targetCurrency}</span>
              </div>
              <small className="rate-hint">
                {r.live != null
                  ? `Aktueller Kurs: 1 ${r.currency} = ${r.live.toFixed(4)} ${targetCurrency}${
                      rateLive && rateDate ? ` (Stand ${rateDate})` : " (Richtwert)"
                    }`
                  : "Aktueller Kurs nicht verfügbar – bitte manuell eintragen."}
              </small>
            </div>
          ))}
        </div>
      )}

      <div className="settings-field">
        <span>Preisberechnung</span>
        <div className="mode-toggle">
          <button
            className={pricingMode === "margin" ? "mode-btn active" : "mode-btn"}
            onClick={() => onPricingModeChange("margin")}
            type="button"
          >
            EK + Marge
          </button>
          <button
            className={pricingMode === "market" ? "mode-btn active" : "mode-btn"}
            onClick={() => onPricingModeChange("market")}
            type="button"
          >
            Marktpreis
          </button>
        </div>
      </div>

      {pricingMode === "market" && (
        <label className="settings-field">
          <span>Abzug vom Marktpreis</span>
          <input
            max={99}
            min={0}
            onChange={(e) => onMarketDiscountChange(Number(e.target.value))}
            step={0.5}
            type="number"
            value={marketDiscount}
          />
        </label>
      )}
    </aside>
  );
}
