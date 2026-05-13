import { Icon } from "./Icon";
import type { ProductRow, RowEdit } from "../types";

type Props = {
  products: ProductRow[];
  filteredProducts: ProductRow[];
  edits: Record<number, RowEdit>;
  margin: number;
  pricingMode: "margin" | "market";
  marketPrices: Record<string, number>;
  marketDiscount: number;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  onEdit: (rowId: number, field: keyof RowEdit, value: number | null) => void;
};

export function ProductTable({
  products,
  filteredProducts,
  edits,
  margin,
  pricingMode,
  marketPrices,
  marketDiscount,
  searchQuery,
  onSearchChange,
  onEdit,
}: Props) {
  return (
    <div className="table-card">
      <div className="table-heading">
        <div>
          <span>Vorschau</span>
          <h2>
            Erkannte Artikel
            {products.length > 0 && (
              <span className="heading-count">
                {" "}
                — {filteredProducts.length}
                {searchQuery ? ` von ${products.length}` : ""} Positionen
              </span>
            )}
          </h2>
        </div>
      </div>

      {products.length > 0 && (
        <div className="table-filter-bar">
          <span className="filter-label">Filtern</span>
          <input
            className="search-input"
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Bezeichnung, SKU, EAN, Farbe, Grösse …"
            type="search"
            value={searchQuery}
          />
          {searchQuery && (
            <button className="filter-clear" onClick={() => onSearchChange("")} type="button">
              ✕ löschen
            </button>
          )}
        </div>
      )}

      {products.length > 0 ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>SKU</th>
                <th>EAN</th>
                <th>Bezeichnung</th>
                <th>Grösse</th>
                <th>Farbe</th>
                <th>Verfügbar</th>
                <th>EK/Stk</th>
                <th>Marktpreis</th>
                <th>VK/Stk (ca.)</th>
                <th>Marge %</th>
                <th>Menge</th>
                <th>VK Total</th>
                <th>VK manuell</th>
              </tr>
            </thead>
            <tbody>
              {filteredProducts.map((row) => {
                const edit = edits[row.row_id];
                const rowMargin = (edit?.margin_pct ?? margin) / 100;
                const mp = row.ean ? marketPrices[row.ean] : undefined;
                const vkFromMarket = mp != null ? mp * (1 - marketDiscount / 100) : null;
                const vkFromMargin =
                  row.unit_price != null && rowMargin < 1
                    ? row.unit_price / (1 - rowMargin)
                    : null;
                const vkCalc =
                  edit?.vk_manual != null
                    ? edit.vk_manual
                    : pricingMode === "market"
                    ? (vkFromMarket ?? vkFromMargin)
                    : vkFromMargin;
                const vkIsMarketFallback =
                  pricingMode === "market" && mp == null && vkCalc != null;
                const currency = row.currency ?? "";

                return (
                  <tr key={row.row_id}>
                    <td>{row.sku ?? "-"}</td>
                    <td style={{ fontFamily: "monospace", fontSize: 12 }}>{row.ean ?? "-"}</td>
                    <td>{row.product_name ?? "-"}</td>
                    <td>{row.size ?? "-"}</td>
                    <td>{row.color ?? "-"}</td>
                    <td style={{ textAlign: "right" }}>{row.available_qty ?? "-"}</td>
                    <td style={{ textAlign: "right" }}>
                      {row.unit_price != null ? `${row.unit_price.toFixed(2)} ${currency}` : "-"}
                    </td>
                    <td style={{ textAlign: "right" }}>
                      {mp != null ? `CHF ${mp.toFixed(2)}` : "-"}
                    </td>
                    <td
                      style={{
                        textAlign: "right",
                        fontWeight: 700,
                        color: vkIsMarketFallback ? "var(--amp-muted)" : "var(--amp-navy)",
                        fontStyle: vkIsMarketFallback ? "italic" : "normal",
                      }}
                    >
                      {vkCalc != null
                        ? `${vkCalc.toFixed(2)} ${currency}${vkIsMarketFallback ? " *" : ""}`
                        : "-"}
                    </td>
                    <td>
                      <input
                        className="qty-input"
                        max={99}
                        min={0}
                        onChange={(e) =>
                          onEdit(row.row_id, "margin_pct", Number(e.target.value))
                        }
                        step={0.5}
                        type="number"
                        value={edit?.margin_pct ?? margin}
                      />
                    </td>
                    <td>
                      <input
                        className="qty-input"
                        min={0}
                        onChange={(e) =>
                          onEdit(
                            row.row_id,
                            "ordered_qty",
                            e.target.value ? Number(e.target.value) : null
                          )
                        }
                        placeholder="0"
                        type="number"
                        value={edit?.ordered_qty ?? ""}
                      />
                    </td>
                    <td style={{ textAlign: "right", fontWeight: 700, color: "var(--amp-navy)" }}>
                      {vkCalc != null && edit?.ordered_qty != null && edit.ordered_qty > 0
                        ? `${(vkCalc * edit.ordered_qty).toFixed(2)} ${currency}`
                        : "-"}
                    </td>
                    <td>
                      <input
                        className="qty-input"
                        min={0}
                        onChange={(e) =>
                          onEdit(
                            row.row_id,
                            "vk_manual",
                            e.target.value ? Number(e.target.value) : null
                          )
                        }
                        placeholder="auto"
                        step={0.01}
                        type="number"
                        value={edit?.vk_manual ?? ""}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="table-empty">
          <Icon name="box" size={32} />
          <p>
            {searchQuery
              ? `Keine Treffer für «${searchQuery}»`
              : "Noch keine Artikel extrahiert."}
          </p>
        </div>
      )}
    </div>
  );
}
