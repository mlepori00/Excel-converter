import type { RefObject } from "react";

import { Icon } from "./Icon";
import type { ParseResult, Stage } from "../types";

type Props = {
  stage: Stage;
  isLoading: boolean;
  hasFile: boolean;
  parseResult: ParseResult | null;
  inputRef: RefObject<HTMLInputElement | null>;
  onFile: (file: File | undefined) => void;
  onReset: () => void;
};

export function ImportCard({ stage, isLoading, hasFile, parseResult, inputRef, onFile, onReset }: Props) {
  return (
    <div
      className={hasFile ? "card import-card has-file" : "card import-card"}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => { e.preventDefault(); onFile(e.dataTransfer.files[0]); }}
    >
      <input
        accept=".xlsx,.xls,.csv"
        onChange={(e) => onFile(e.target.files?.[0])}
        ref={inputRef}
        type="file"
      />
      <div className="drop-art">
        <Icon name={isLoading ? "loader" : hasFile ? "check" : "upload"} size={36} />
      </div>
      <span className="drop-label">
        {stage === "parsing"
          ? "Wird gelesen …"
          : stage === "extracting"
          ? "Claude läuft …"
          : hasFile
          ? "Geladen"
          : "Import"}
      </span>
      <strong className="import-filename">{parseResult?.filename ?? "Excel oder CSV"}</strong>
      {hasFile && (
        <p className="import-meta">
          {parseResult!.row_count} Zeilen · {parseResult!.column_count} Spalten
        </p>
      )}
      <button disabled={isLoading} onClick={() => inputRef.current?.click()} type="button">
        {hasFile ? "Datei ersetzen" : "Datei hochladen"}
      </button>
      {hasFile && (
        <button className="reset-button" onClick={onReset} type="button">
          Neue Offerte
        </button>
      )}
    </div>
  );
}
