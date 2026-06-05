import { useEffect, useState, type MouseEvent } from "react";

import {
  apiDownloadOfferFile,
  apiGetOffer,
  apiListOffers,
  apiOfferTree,
  apiPreviewOfferFile,
  apiSetOfferStatus,
  downloadBlob,
} from "../api";
import type { OfferDetail, OfferStatusValue, OfferSummary, TreeYear } from "../types";
import { Icon } from "./Icon";

type PreviewKind = "original" | "generated";
type PreviewState = { html: string; title: string };

const STATUS_LABELS: Record<OfferStatusValue, string> = {
  erstellt: "Erstellt",
  versendet: "Versendet",
  bestellung_erhalten: "Bestellung erhalten",
  abgeschlossen: "Abgeschlossen",
};
const STATUS_ORDER: OfferStatusValue[] = [
  "erstellt",
  "versendet",
  "bestellung_erhalten",
  "abgeschlossen",
];

type Filters = { jahr?: number; marke?: string; lieferant?: string };

function fmtDate(iso: string | null): string {
  if (!iso) return "–";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "–" : d.toLocaleDateString("de-CH");
}

function fmtNum(v: number | null): string {
  return v == null ? "–" : v.toLocaleString("de-CH", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function ArchiveView() {
  const [tree, setTree] = useState<TreeYear[]>([]);
  const [filters, setFilters] = useState<Filters>({});
  const [q, setQ] = useState("");
  const [offers, setOffers] = useState<OfferSummary[]>([]);
  const [selected, setSelected] = useState<OfferDetail | null>(null);
  const [expandedYears, setExpandedYears] = useState<Set<number>>(new Set());
  const [expandedBrands, setExpandedBrands] = useState<Set<string>>(new Set());
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState<PreviewState | null>(null);
  const [previewLoading, setPreviewLoading] = useState<string | null>(null);

  function refreshTree() {
    apiOfferTree().then(setTree).catch(() => undefined);
  }

  useEffect(refreshTree, []);

  useEffect(() => {
    setLoading(true);
    setError("");
    apiListOffers({ ...filters, q })
      .then(setOffers)
      .catch((e) => setError(e instanceof Error ? e.message : "Laden fehlgeschlagen"))
      .finally(() => setLoading(false));
  }, [filters, q]);

  function toggleYear(jahr: number) {
    setExpandedYears((prev) => {
      const next = new Set(prev);
      next.has(jahr) ? next.delete(jahr) : next.add(jahr);
      return next;
    });
  }
  function toggleBrand(key: string) {
    setExpandedBrands((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }

  async function openOffer(id: number) {
    try {
      setSelected(await apiGetOffer(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Offerte konnte nicht geladen werden");
    }
  }

  async function changeStatus(status: OfferStatusValue) {
    if (!selected) return;
    try {
      const updated = await apiSetOfferStatus(selected.id, status);
      setSelected({ ...selected, status: updated.status });
      setOffers((prev) => prev.map((o) => (o.id === selected.id ? { ...o, status } : o)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Status konnte nicht geändert werden");
    }
  }

  async function download(which: "original" | "generated") {
    if (!selected) return;
    try {
      const blob = await apiDownloadOfferFile(selected.id, which);
      const name = which === "original" ? selected.original_filename : selected.generated_filename;
      downloadBlob(blob, name || `${which}.xlsx`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Download fehlgeschlagen");
    }
  }

  async function openPreview(e: MouseEvent, o: OfferSummary, which: PreviewKind) {
    e.stopPropagation();
    const key = `${o.id}:${which}`;
    setPreviewLoading(key);
    setError("");
    try {
      const html = await apiPreviewOfferFile(o.id, which);
      const title =
        which === "original"
          ? `Lieferanten-Offerte – ${o.lieferant}`
          : `Unsere Offerte – ${o.marke}`;
      setPreview({ html, title });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Vorschau fehlgeschlagen");
    } finally {
      setPreviewLoading(null);
    }
  }

  function closePreview() {
    setPreview(null);
  }

  const isAll = !filters.jahr && !filters.marke && !filters.lieferant;

  return (
    <section className="archive">
      <aside className="archive-tree">
        <button
          className={isAll ? "tree-node tree-all active" : "tree-node tree-all"}
          onClick={() => setFilters({})}
          type="button"
        >
          Alle Offerten
        </button>

        {tree.map((y) => {
          const yOpen = expandedYears.has(y.jahr);
          const yActive = filters.jahr === y.jahr && !filters.marke;
          return (
            <div key={y.jahr} className="tree-year">
              <button
                className={yActive ? "tree-node active" : "tree-node"}
                onClick={() => {
                  toggleYear(y.jahr);
                  setFilters({ jahr: y.jahr });
                }}
                type="button"
              >
                <span className="tree-caret">{yOpen ? "▾" : "▸"}</span>
                {y.jahr}
                <span className="tree-count">{y.count}</span>
              </button>

              {yOpen &&
                y.marken.map((m) => {
                  const bKey = `${y.jahr}|${m.marke}`;
                  const bOpen = expandedBrands.has(bKey);
                  const bActive = filters.jahr === y.jahr && filters.marke === m.marke && !filters.lieferant;
                  return (
                    <div key={bKey} className="tree-brand">
                      <button
                        className={bActive ? "tree-node tree-l2 active" : "tree-node tree-l2"}
                        onClick={() => {
                          toggleBrand(bKey);
                          setFilters({ jahr: y.jahr, marke: m.marke });
                        }}
                        type="button"
                      >
                        <span className="tree-caret">{bOpen ? "▾" : "▸"}</span>
                        {m.marke}
                        <span className="tree-count">{m.count}</span>
                      </button>

                      {bOpen &&
                        m.lieferanten.map((s) => {
                          const sActive =
                            filters.jahr === y.jahr &&
                            filters.marke === m.marke &&
                            filters.lieferant === s.lieferant;
                          return (
                            <button
                              key={s.lieferant}
                              className={sActive ? "tree-node tree-l3 active" : "tree-node tree-l3"}
                              onClick={() =>
                                setFilters({ jahr: y.jahr, marke: m.marke, lieferant: s.lieferant })
                              }
                              type="button"
                            >
                              {s.lieferant}
                              <span className="tree-count">{s.count}</span>
                            </button>
                          );
                        })}
                    </div>
                  );
                })}
            </div>
          );
        })}
      </aside>

      <div className="archive-main">
        <input
          className="archive-search"
          onChange={(e) => setQ(e.target.value)}
          placeholder="Suchen (Marke, Lieferant …)"
          value={q}
        />

        {error && <p className="login-error">{error}</p>}

        {loading ? (
          <p className="archive-empty">Lädt …</p>
        ) : offers.length === 0 ? (
          <p className="archive-empty">Keine Offerten gefunden.</p>
        ) : (
          <table className="archive-table">
            <thead>
              <tr>
                <th>Datum</th>
                <th>Marke</th>
                <th>Lieferant</th>
                <th>Lieferanten-Offerte</th>
                <th>Unsere Offerte</th>
                <th>Ersteller</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {offers.map((o) => (
                <tr key={o.id} onClick={() => void openOffer(o.id)}>
                  <td>{fmtDate(o.created_at)}</td>
                  <td>{o.marke}</td>
                  <td>{o.lieferant}</td>
                  <td>
                    <button
                      className="preview-btn"
                      disabled={previewLoading === `${o.id}:original`}
                      onClick={(e) => void openPreview(e, o, "original")}
                      type="button"
                    >
                      <Icon name={previewLoading === `${o.id}:original` ? "loader" : "file"} size={15} />
                      {previewLoading === `${o.id}:original` ? "Lädt …" : "Ansehen"}
                    </button>
                  </td>
                  <td>
                    <button
                      className="preview-btn"
                      disabled={previewLoading === `${o.id}:generated`}
                      onClick={(e) => void openPreview(e, o, "generated")}
                      type="button"
                    >
                      <Icon name={previewLoading === `${o.id}:generated` ? "loader" : "file"} size={15} />
                      {previewLoading === `${o.id}:generated` ? "Lädt …" : "Ansehen"}
                    </button>
                  </td>
                  <td>{o.created_by_name}</td>
                  <td>
                    <span className={`status-badge status-${o.status}`}>
                      {STATUS_LABELS[o.status]}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selected && (
        <div className="modal-overlay" onClick={() => setSelected(null)}>
          <div className="archive-detail" onClick={(e) => e.stopPropagation()}>
            <div className="archive-detail-head">
              <div>
                <h2>
                  {selected.marke} — {selected.lieferant}
                </h2>
                <p className="archive-detail-meta">
                  {selected.jahr} · {fmtDate(selected.created_at)} · {selected.created_by_name}
                </p>
              </div>
              <button className="archive-close" onClick={() => setSelected(null)} type="button">
                ✕
              </button>
            </div>

            <div className="archive-detail-controls">
              <label className="settings-field">
                <span>Status</span>
                <select
                  onChange={(e) => void changeStatus(e.target.value as OfferStatusValue)}
                  value={selected.status}
                >
                  {STATUS_ORDER.map((s) => (
                    <option key={s} value={s}>
                      {STATUS_LABELS[s]}
                    </option>
                  ))}
                </select>
              </label>
              <div className="archive-downloads">
                <button onClick={() => void download("generated")} type="button">
                  Offerte herunterladen
                </button>
                <button
                  className="ghost"
                  disabled={!selected.original_filename}
                  onClick={() => void download("original")}
                  type="button"
                >
                  Original herunterladen
                </button>
              </div>
            </div>

            <div className="archive-lines-wrap">
              <table className="archive-table archive-lines">
                <thead>
                  <tr>
                    <th>Pos</th>
                    <th>Bezeichnung</th>
                    <th>SKU</th>
                    <th>Grösse</th>
                    <th>Menge</th>
                    <th>VK/Stk</th>
                    <th>VK Total</th>
                  </tr>
                </thead>
                <tbody>
                  {selected.line_items.map((li) => (
                    <tr key={li.position}>
                      <td>{li.position + 1}</td>
                      <td>{li.product_name ?? "–"}</td>
                      <td>{li.sku ?? "–"}</td>
                      <td>{li.size ?? "–"}</td>
                      <td>{li.ordered_qty ?? "–"}</td>
                      <td>{fmtNum(li.vk_unit)}</td>
                      <td>{fmtNum(li.vk_total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {preview && (
        <div className="preview-overlay" onClick={closePreview}>
          <div className="preview-box" onClick={(e) => e.stopPropagation()}>
            <div className="preview-head">
              <span className="preview-title">{preview.title}</span>
              <button className="archive-close" onClick={closePreview} type="button">
                ✕
              </button>
            </div>
            <iframe
              className="preview-frame"
              sandbox=""
              srcDoc={preview.html}
              title={preview.title}
            />
          </div>
        </div>
      )}
    </section>
  );
}
