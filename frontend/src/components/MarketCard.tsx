import type { ProductRow } from "../types";

type Props = {
  hasFile: boolean;
  products: ProductRow[];
  marketPrices: Record<string, number>;
  scrapingProgress: { done: number; total: number } | null;
  scrapingStatus: string;
  scrapeEnabled: boolean;
  onScrapeToggle: (checked: boolean) => void;
};

export function MarketCard({
  hasFile,
  products,
  marketPrices,
  scrapingProgress,
  scrapingStatus,
  scrapeEnabled,
  onScrapeToggle,
}: Props) {
  if (!hasFile || products.length === 0) {
    return (
      <div className="card market-card">
        <p className="card-label">Marktpreise</p>
        <p className="actions-empty">Datei laden um Marktpreise zu suchen</p>
      </div>
    );
  }

  const eanCount = products.filter((p) => p.ean?.trim()).length;
  const secs = Math.ceil(eanCount * 1.6);
  const timeStr = secs >= 60 ? `ca. ${Math.round(secs / 60)} min` : `ca. ${secs} s`;
  const foundCount = Object.keys(marketPrices).length;

  return (
    <div className="card market-card">
      <p className="card-label">Marktpreise</p>

      <div className="market-stats">
        <div className="market-stat">
          <strong>{eanCount}</strong>
          <span>EANs gefunden</span>
        </div>
        <div className="market-stat-divider" />
        <div className="market-stat">
          <strong>{timeStr}</strong>
          <span>geschätzte Dauer</span>
        </div>
        <div className="market-stat-divider" />
        <div className="market-stat">
          <strong>{foundCount > 0 ? foundCount : "—"}</strong>
          <span>Preise gefunden</span>
        </div>
      </div>

      <p className="market-desc">
        Aktuelle Marktpreise von Toppreise.ch abrufen und als Grundlage für die VK-Kalkulation
        verwenden.
      </p>

      {scrapingProgress !== null && (
        <div className="market-progress">
          <div
            className="market-progress-bar"
            style={{ width: `${Math.round((scrapingProgress.done / scrapingProgress.total) * 100)}%` }}
          />
          <span>
            {scrapingProgress.done} / {scrapingProgress.total}
          </span>
        </div>
      )}
      {scrapingStatus && scrapingProgress === null && (
        <p className="market-status">{scrapingStatus}</p>
      )}

      <button
        className={scrapeEnabled ? "market-btn market-btn--stop" : "market-btn market-btn--start"}
        disabled={eanCount === 0}
        onClick={() => onScrapeToggle(!scrapeEnabled)}
        type="button"
      >
        {scrapeEnabled ? "Suche stoppen" : "Marktpreise suchen"}
      </button>
    </div>
  );
}
