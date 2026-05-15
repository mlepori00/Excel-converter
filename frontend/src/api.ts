import type { ParseResult, ProductRow, RowEdit } from "./types";

export const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const _TOKEN = import.meta.env.VITE_API_TOKEN ?? "";

export function _authHeader(): Record<string, string> {
  return _TOKEN ? { Authorization: `Bearer ${_TOKEN}` } : {};
}

function _extractDetail(err: unknown): string {
  if (!err || typeof err !== "object") return String(err ?? "Unbekannter Fehler");
  const detail = (err as Record<string, unknown>).detail;
  if (Array.isArray(detail))
    return detail.map((e) => (typeof e === "object" && e !== null ? (e as Record<string, unknown>).msg ?? JSON.stringify(e) : String(e))).join(" | ");
  return String(detail ?? "Unbekannter Fehler");
}

export async function apiParse(file: File, forceReparse = false): Promise<ParseResult> {
  const form = new FormData();
  form.append("file", file);
  if (forceReparse) form.append("force_reparse", "true");
  const resp = await fetch(`${API}/api/offer/parse`, { method: "POST", headers: _authHeader(), body: form });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(_extractDetail(err));
  }
  return resp.json() as Promise<ParseResult>;
}

export async function apiExtract(fileId: string, profileName?: string): Promise<ProductRow[]> {
  const resp = await fetch(`${API}/api/offer/extract`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ..._authHeader() },
    body: JSON.stringify({ file_id: fileId, force_api: true, profile_name: profileName ?? null }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail ?? "Extraktions-Fehler");
  }
  const data = (await resp.json()) as { products: ProductRow[] };
  return data.products;
}

export async function apiExport(
  fileId: string,
  supplierName: string,
  targetCurrency: string,
  defaultMargin: number,
  products: ProductRow[],
  edits: Record<number, RowEdit>,
  marketPrices: Record<string, number>
): Promise<Blob> {
  const rows = products.map((p) => {
    const edit = edits[p.row_id] ?? { ordered_qty: null, vk_manual: null, margin_pct: defaultMargin };
    return {
      sku: p.sku,
      ean: p.ean,
      product_name: p.product_name,
      size: p.size,
      color: p.color,
      category: p.category,
      unit_price: p.unit_price,
      currency: p.currency,
      discount_pct: p.discount_pct,
      notes: p.notes,
      available_qty: p.available_qty,
      ordered_qty: edit.ordered_qty,
      vk_manual: edit.vk_manual,
      margin_pct: edit.margin_pct,
      market_price: p.ean ? (marketPrices[p.ean] ?? null) : null,
    };
  });

  const resp = await fetch(`${API}/api/offer/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ..._authHeader() },
    body: JSON.stringify({
      file_id: fileId,
      supplier_name: supplierName,
      created_by: "AMP Sport GmbH",
      target_currency: targetCurrency,
      valid_days: 30,
      default_margin_pct: defaultMargin,
      rows,
    }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(_extractDetail(err));
  }
  return resp.blob();
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function inferSupplierName(filename: string): string {
  const cleaned = filename
    .replace(/\.[^.]+$/, "")
    .replace(/\(\d+\)/g, "")
    .replace(/offerte/gi, "")
    .replace(/\d{6,}/g, "")
    .replace(/\b\d+\b/g, "")
    .replace(/[()_\-.]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!cleaned) return "";
  return cleaned
    .split(" ")
    .filter(Boolean)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase())
    .join(" ");
}
