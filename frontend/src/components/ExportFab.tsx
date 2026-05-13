import { Icon } from "./Icon";
import type { ProductRow, Stage } from "../types";

type Props = {
  canExport: boolean;
  isLoading: boolean;
  stage: Stage;
  filteredProducts: ProductRow[];
  supplierName: string;
  onExport: () => void;
};

export function ExportFab({ canExport, isLoading, stage, filteredProducts, supplierName, onExport }: Props) {
  return (
    <button
      className={canExport && !isLoading ? "fab-export" : "fab-export fab-export--disabled"}
      disabled={!canExport || isLoading}
      onClick={onExport}
      type="button"
    >
      <span className="fab-export-icon">
        <Icon name={stage === "exporting" ? "loader" : "download"} size={22} />
      </span>
      <span className="fab-export-text">
        <strong>{stage === "exporting" ? "Wird erstellt …" : "Offerte als Excel laden"}</strong>
        <small>
          {canExport
            ? `${filteredProducts.length} Artikel · ${supplierName}`
            : "Marke eintragen um fortzufahren"}
        </small>
      </span>
    </button>
  );
}
