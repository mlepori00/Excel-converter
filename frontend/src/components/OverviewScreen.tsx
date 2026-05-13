import { Icon } from "./Icon";
import type { ExportSummary } from "../types";

type Props = {
  summary: ExportSummary;
  onNewOffer: () => void;
  onBack: () => void;
};

export function OverviewScreen({ summary, onNewOffer, onBack }: Props) {
  return (
    <div className="overview-screen">
      <div className="overview-card">
        <div className="overview-icon">
          <Icon name="check" size={32} strokeWidth={2.5} />
        </div>

        <p className="overview-eyebrow">Export erfolgreich</p>
        <h2 className="overview-heading">Offerte erstellt</h2>

        <dl className="overview-details">
          <div>
            <dt>Lieferant</dt>
            <dd>{summary.supplierName}</dd>
          </div>
          <div>
            <dt>Artikel</dt>
            <dd>{summary.articleCount}</dd>
          </div>
          <div>
            <dt>Währung</dt>
            <dd>{summary.currency}</dd>
          </div>
          <div>
            <dt>Datei</dt>
            <dd className="overview-filename">{summary.filename}</dd>
          </div>
        </dl>

        <div className="overview-actions">
          <button className="overview-btn-primary" onClick={onNewOffer} type="button">
            Neue Offerte starten
          </button>
          <button className="overview-btn-ghost" onClick={onBack} type="button">
            Zurück zum Entwurf
          </button>
        </div>
      </div>
    </div>
  );
}
