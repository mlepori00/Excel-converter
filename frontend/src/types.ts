export type AuthUser = {
  id: number;
  email: string;
  name: string;
  must_change_password: boolean;
};

export type Stage =
  | "empty"
  | "parsing"
  | "parsed"
  | "extracting"
  | "ready"
  | "exporting"
  | "exported";

export type ExportSummary = {
  supplierName: string;
  marke: string;
  articleCount: number;
  currency: string;
  filename: string;
  archived: boolean;
};

export type ProductRow = {
  row_id: number;
  sku: string | null;
  ean: string | null;
  product_name: string | null;
  size: string | null;
  color: string | null;
  category: string | null;
  unit_price: number | null;
  currency: string | null;
  ordered_qty: number | null;
  available_qty: number | null;
  discount_pct: number | null;
  notes: string | null;
  status: string;
};

export type ParseResult = {
  file_id: string;
  filename: string;
  sheets: string[];
  selected_sheet: string | null;
  row_count: number;
  column_count: number;
  detected_currency: string | null;
  layout_type: string | null;
  was_unpivoted: boolean;
  sanitizer_removed: number;
  extraction_mode: string;
  products: ProductRow[];
  api_cost_estimate_chf: number | null;
  map_columns_cost_estimate_chf: number | null;
};

export type RowEdit = {
  ordered_qty: number | null;
  vk_manual: number | null;
  margin_pct: number;
};

export type OfferStatusValue =
  | "erstellt"
  | "versendet"
  | "bestellung_erhalten"
  | "abgeschlossen";

export type OfferSummary = {
  id: number;
  jahr: number;
  marke: string;
  lieferant: string;
  status: OfferStatusValue;
  created_by_name: string;
  created_at: string | null;
  title: string | null;
  original_filename: string;
  generated_filename: string;
};

export type ArchiveLine = {
  position: number;
  sku: string | null;
  ean: string | null;
  product_name: string | null;
  size: string | null;
  color: string | null;
  category: string | null;
  unit_price: number | null;
  currency: string | null;
  ordered_qty: number | null;
  available_qty: number | null;
  discount_pct: number | null;
  vk_unit: number | null;
  vk_total: number | null;
  margin_actual: number | null;
  notes: string | null;
};

export type OfferDetail = OfferSummary & { line_items: ArchiveLine[] };

export type TreeSupplier = { lieferant: string; count: number };
export type TreeBrand = { marke: string; count: number; lieferanten: TreeSupplier[] };
export type TreeYear = { jahr: number; count: number; marken: TreeBrand[] };

export type MapColumnsResult = {
  mapped_fields: Record<string, string>; // {canonical_field: original_column}
  columns_total: number;
  columns_mapped: number;
  unmapped_columns: string[];
  products: ProductRow[];
};
