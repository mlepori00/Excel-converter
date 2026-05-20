import type { ProductRow } from "../types";

type Props = {
  hasFile: boolean;
  products: ProductRow[];
  marketPrices: Record<string, number>;
  scrapingProgress: { done: number; total: number } | null;
  scrapingStatus: string;
  isSampling: boolean;
  sampleResult: { hit: number; total: number; eans: Array<{ ean: string; found: boolean }> } | null;
  onSample: () => void;
  onScrapeAll: () => void;
  onStop: () => void;
};

export function MarketCard({
  hasFile,
  products,
  marketPrices,
  scrapingProgress,
  scrapingStatus,
  isSampling,
  sampleResult,
  onSample,
  onScrapeAll,
  onStop,
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
  const isBusy = scrapingProgress !== null || isSampling;

  const hitPct = sampleResult
    ? Math.round((sampleResult.hit / sampleResult.total) * 100)
    : null;
  const expectedFull =
    sampleResult && sampleResult.hit > 0
      ? Math.round(eanCount * (sampleResult.hit / sampleResult.total))
      : null;

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

      {sampleResult && !isBusy && (
        <div
          className={`market-sample-badge ${
            hitPct! >= 50 ? "market-sample-badge--ok" : "market-sample-badge--warn"
          }`}
        >
          <span className="market-sample-rate">
            {sampleResult.hit}/{sampleResult.total} Stichproben gefunden ({hitPct}%)
          </span>
          {expectedFull !== null ? (
            <span className="market-sample-estimate">
              ~ {expectedFull} von {eanCount} EANs zu erwarten
            </span>
          ) : (
            <span className="market-sample-estimate">Keine Treffer erwartet</span>
          )}
          <div className="market-sample-eans">
            {sampleResult.eans.map(({ ean, found }) => (
              <span
                key={ean}
                className={`market-sample-ean ${found ? "market-sample-ean--found" : "market-sample-ean--miss"}`}
              >
                {found ? "✓" : "✗"} {ean}
              </span>
            ))}
          </div>
        </div>
      )}

      {scrapingProgress !== null && (
        <div className="market-progress">
          <div
            className="market-progress-bar"
            style={{
              width: `${Math.round((scrapingProgress.done / scrapingProgress.total) * 100)}%`,
            }}
          />
          <span>
            {isSampling ? "Stichprobe " : ""}
            {scrapingProgress.done} / {scrapingProgress.total}
          </span>
        </div>
      )}

      {scrapingStatus && !isBusy && (
        <p className="market-status">{scrapingStatus}</p>
      )}

      {isBusy ? (
        <button className="market-btn market-btn--stop" onClick={onStop} type="button">
          Stoppen
        </button>
      ) : sampleResult ? (
        <div className="market-btn-row">
          <button
            className="market-btn market-btn--start"
            disabled={eanCount === 0}
            onClick={onScrapeAll}
            type="button"
          >
            Alle {eanCount} EANs laden
          </button>
          <button
            className="market-btn market-btn--stop"
            onClick={onSample}
            type="button"
          >
            Neue Stichprobe
          </button>
        </div>
      ) : (
        <button
          className="market-btn market-btn--start"
          disabled={eanCount === 0}
          onClick={onSample}
          type="button"
        >
          Stichprobe prüfen
        </button>
      )}
    </div>
  );
}
