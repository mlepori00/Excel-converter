import type {
  AuthUser,
  MapColumnsResult,
  OfferDetail,
  OfferStatusValue,
  OfferSummary,
  ParseResult,
  ProductRow,
  RowEdit,
  TreeYear,
} from "./types";

export const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// JWT is obtained at login and kept across reloads in localStorage.
const TOKEN_KEY = "oc_token";
let _token: string | null =
  typeof localStorage !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
let _onAuthError: (() => void) | null = null;

export function setToken(token: string | null): void {
  _token = token;
  if (typeof localStorage === "undefined") return;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function getToken(): string | null {
  return _token;
}

/** Register a callback invoked whenever the server rejects the token (401). */
export function setAuthErrorHandler(fn: (() => void) | null): void {
  _onAuthError = fn;
}

export function _authHeader(): Record<string, string> {
  return _token ? { Authorization: `Bearer ${_token}` } : {};
}

/** Clear the token and notify the app when a request comes back unauthorized. */
export function handleUnauthorized(status: number): boolean {
  if (status !== 401) return false;
  setToken(null);
  _onAuthError?.();
  return true;
}

export async function apiLogin(email: string, password: string): Promise<AuthUser> {
  const resp = await fetch(`${API}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(_extractDetail(err));
  }
  const data = (await resp.json()) as { access_token: string; user: AuthUser };
  setToken(data.access_token);
  return data.user;
}

export async function apiMe(): Promise<AuthUser> {
  const resp = await fetch(`${API}/api/auth/me`, { headers: { ..._authHeader() } });
  if (!resp.ok) {
    handleUnauthorized(resp.status);
    throw new Error("Nicht authentifiziert");
  }
  return resp.json() as Promise<AuthUser>;
}

export async function apiChangePassword(
  currentPassword: string,
  newPassword: string
): Promise<AuthUser> {
  const resp = await fetch(`${API}/api/auth/change-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ..._authHeader() },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  if (!resp.ok) {
    handleUnauthorized(resp.status);
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(_extractDetail(err));
  }
  return resp.json() as Promise<AuthUser>;
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
    handleUnauthorized(resp.status);
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(_extractDetail(err));
  }
  return resp.json() as Promise<ParseResult>;
}

export async function apiMapColumns(fileId: string): Promise<MapColumnsResult> {
  const resp = await fetch(`${API}/api/offer/map-columns`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ..._authHeader() },
    body: JSON.stringify({ file_id: fileId }),
  });
  if (!resp.ok) {
    handleUnauthorized(resp.status);
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(_extractDetail(err));
  }
  return resp.json() as Promise<MapColumnsResult>;
}

export async function apiExtract(fileId: string, profileName?: string): Promise<ProductRow[]> {
  const resp = await fetch(`${API}/api/offer/extract`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ..._authHeader() },
    body: JSON.stringify({ file_id: fileId, force_api: true, profile_name: profileName ?? null }),
  });
  if (!resp.ok) {
    handleUnauthorized(resp.status);
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
  marketPrices: Record<string, number>,
  createdBy: string,
  marke: string
): Promise<{ blob: Blob; offerId: number | null }> {
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
      marke,
      created_by: createdBy,
      target_currency: targetCurrency,
      valid_days: 30,
      default_margin_pct: defaultMargin,
      rows,
    }),
  });
  if (!resp.ok) {
    handleUnauthorized(resp.status);
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(_extractDetail(err));
  }
  const offerIdHeader = resp.headers.get("X-Offer-Id");
  const blob = await resp.blob();
  return { blob, offerId: offerIdHeader ? Number(offerIdHeader) : null };
}

export type BrandSupplierIndex = {
  /** All distinct brand names, alphabetically. */
  brands: string[];
  /** All distinct supplier names across every brand, alphabetically. */
  allSuppliers: string[];
  /** Suppliers seen per brand (key = brand name), for prioritized suggestions. */
  suppliersByBrand: Record<string, string[]>;
};

/**
 * Build the brand/supplier suggestion index from the archive tree so the
 * create flow can offer existing names (avoids duplicate / mis-spelled entries).
 */
export async function apiBrandSupplierIndex(): Promise<BrandSupplierIndex> {
  const tree = await apiOfferTree();
  const brandSet = new Set<string>();
  const allSet = new Set<string>();
  const byBrand: Record<string, Set<string>> = {};
  tree.forEach((year) =>
    year.marken.forEach((m) => {
      brandSet.add(m.marke);
      (byBrand[m.marke] ??= new Set<string>());
      m.lieferanten.forEach((l) => {
        byBrand[m.marke].add(l.lieferant);
        allSet.add(l.lieferant);
      });
    })
  );
  const sort = (a: string, b: string) => a.localeCompare(b);
  const suppliersByBrand: Record<string, string[]> = {};
  for (const [brand, set] of Object.entries(byBrand)) {
    suppliersByBrand[brand] = [...set].sort(sort);
  }
  return {
    brands: [...brandSet].sort(sort),
    allSuppliers: [...allSet].sort(sort),
    suppliersByBrand,
  };
}

// --- Archive --------------------------------------------------------------

async function _getJson<T>(path: string): Promise<T> {
  const resp = await fetch(`${API}${path}`, { headers: { ..._authHeader() } });
  if (!resp.ok) {
    handleUnauthorized(resp.status);
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(_extractDetail(err));
  }
  return resp.json() as Promise<T>;
}

export async function apiOfferTree(): Promise<TreeYear[]> {
  return _getJson<TreeYear[]>("/api/offers/tree");
}

export async function apiListOffers(params: {
  jahr?: number;
  marke?: string;
  lieferant?: string;
  q?: string;
}): Promise<OfferSummary[]> {
  const sp = new URLSearchParams();
  if (params.jahr != null) sp.set("jahr", String(params.jahr));
  if (params.marke) sp.set("marke", params.marke);
  if (params.lieferant) sp.set("lieferant", params.lieferant);
  if (params.q?.trim()) sp.set("q", params.q.trim());
  const query = sp.toString();
  return _getJson<OfferSummary[]>(`/api/offers${query ? `?${query}` : ""}`);
}

export async function apiGetOffer(id: number): Promise<OfferDetail> {
  return _getJson<OfferDetail>(`/api/offers/${id}`);
}

export async function apiSetOfferStatus(
  id: number,
  status: OfferStatusValue
): Promise<OfferSummary> {
  const resp = await fetch(`${API}/api/offers/${id}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ..._authHeader() },
    body: JSON.stringify({ status }),
  });
  if (!resp.ok) {
    handleUnauthorized(resp.status);
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(_extractDetail(err));
  }
  return resp.json() as Promise<OfferSummary>;
}

export async function apiDownloadOfferFile(
  id: number,
  which: "original" | "generated"
): Promise<Blob> {
  const resp = await fetch(`${API}/api/offers/${id}/${which}`, {
    headers: { ..._authHeader() },
  });
  if (!resp.ok) {
    handleUnauthorized(resp.status);
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(_extractDetail(err));
  }
  return resp.blob();
}

/** Fetch the server-rendered HTML preview of an archived file. */
export async function apiPreviewOfferFile(
  id: number,
  which: "original" | "generated"
): Promise<string> {
  const resp = await fetch(`${API}/api/offers/${id}/preview/${which}`, {
    headers: { ..._authHeader() },
  });
  if (!resp.ok) {
    handleUnauthorized(resp.status);
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(_extractDetail(err));
  }
  return resp.text();
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
