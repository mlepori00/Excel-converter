import { Combobox } from "./Combobox";
import type { ResolveStatus } from "./Combobox";

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
  onSupplierNameChange: (v: string) => void;
  onMarkeChange: (v: string) => void;
  onMarkeStatusChange: (s: ResolveStatus) => void;
  onSupplierStatusChange: (s: ResolveStatus) => void;
  onMarginChange: (v: number) => void;
  onCurrencyChange: (v: string) => void;
  onPricingModeChange: (v: "margin" | "market") => void;
  onMarketDiscountChange: (v: number) => void;
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
  onSupplierNameChange,
  onMarkeChange,
  onMarkeStatusChange,
  onSupplierStatusChange,
  onMarginChange,
  onCurrencyChange,
  onPricingModeChange,
  onMarketDiscountChange,
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
