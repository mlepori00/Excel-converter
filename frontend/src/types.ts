export type Stage =
  | "empty"
  | "parsing"
  | "parsed"
  | "extracting"
  | "ready"
  | "exporting";

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
};

export type RowEdit = {
  ordered_qty: number | null;
  vk_manual: number | null;
  margin_pct: number;
};
