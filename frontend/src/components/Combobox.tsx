import { useEffect, useMemo, useRef, useState } from "react";

/**
 * Resolution status of the current value against the known options.
 * - "empty":       no value entered
 * - "existing":    value matches a known option (case/whitespace-insensitive)
 * - "new":         value is genuinely new, no similar option exists
 * - "unconfirmed": a similar option exists and the user has not yet decided
 *                  (pick a suggestion or confirm "Neu anlegen")
 */
export type ResolveStatus = "empty" | "existing" | "new" | "unconfirmed";

type Props = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  onStatusChange?: (status: ResolveStatus) => void;
  /** Full list of known options (canonical spellings). */
  options: string[];
  /** Options shown first under their own header (e.g. suppliers of the brand). */
  priorityOptions?: string[];
  priorityLabel?: string;
  restLabel?: string;
  placeholder?: string;
};

/** Strip diacritics, lowercase, collapse whitespace. */
function norm(s: string): string {
  return s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

/** Levenshtein edit distance. */
function lev(a: string, b: string): number {
  const m = a.length;
  const n = b.length;
  if (m === 0) return n;
  if (n === 0) return m;
  const dp = Array.from({ length: m + 1 }, (_, i) => i);
  for (let j = 1; j <= n; j++) {
    let prev = dp[0];
    dp[0] = j;
    for (let i = 1; i <= m; i++) {
      const tmp = dp[i];
      dp[i] = Math.min(dp[i] + 1, dp[i - 1] + 1, prev + (a[i - 1] === b[j - 1] ? 0 : 1));
      prev = tmp;
    }
  }
  return dp[m];
}

/** True when two normalized names are close enough to be a likely mis-spelling. */
function isSimilar(qn: string, on: string): boolean {
  if (!qn || !on || qn === on) return false;
  if (qn.length >= 3 && (on.includes(qn) || qn.includes(on))) return true;
  const d = lev(qn, on);
  const maxLen = Math.max(qn.length, on.length);
  return d <= Math.max(1, Math.floor(maxLen * 0.25));
}

export function Combobox({
  label,
  value,
  onChange,
  onStatusChange,
  options,
  priorityOptions = [],
  priorityLabel,
  restLabel,
  placeholder,
}: Props) {
  const [open, setOpen] = useState(false);
  const [confirmedNew, setConfirmedNew] = useState(false);
  const wrapRef = useRef<HTMLDivElement | null>(null);

  const vn = norm(value);

  // Canonical option matching the typed value exactly (ignoring case/spacing).
  const exactMatch = useMemo(
    () => options.find((o) => norm(o) === vn) ?? null,
    [options, vn]
  );

  // Similar-but-not-exact options, used for the duplicate warning.
  const similar = useMemo(() => {
    if (!vn || exactMatch) return [];
    return options.filter((o) => isSimilar(vn, norm(o))).slice(0, 5);
  }, [options, vn, exactMatch]);

  const status: ResolveStatus = !value.trim()
    ? "empty"
    : exactMatch
      ? "existing"
      : similar.length > 0 && !confirmedNew
        ? "unconfirmed"
        : "new";

  // Report status changes upward without causing render loops.
  const lastStatus = useRef<ResolveStatus | null>(null);
  useEffect(() => {
    if (lastStatus.current !== status) {
      lastStatus.current = status;
      onStatusChange?.(status);
    }
  }, [status, onStatusChange]);

  // Filter dropdown contents by the typed query (substring on normalized form).
  const filterList = (list: string[]) =>
    vn ? list.filter((o) => norm(o).includes(vn)) : list;

  const prioFiltered = filterList(priorityOptions);
  const prioSet = new Set(priorityOptions.map(norm));
  const restFiltered = filterList(options).filter((o) => !prioSet.has(norm(o)));

  // Close on outside click / Escape.
  useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function select(option: string) {
    onChange(option);
    setConfirmedNew(false);
    setOpen(false);
  }

  function handleType(next: string) {
    onChange(next);
    setConfirmedNew(false);
    if (!open) setOpen(true);
  }

  const hasDropdown = open && (prioFiltered.length > 0 || restFiltered.length > 0);

  return (
    <div className="settings-field combobox" ref={wrapRef}>
      <span>{label}</span>
      <div className="combobox__control">
        <input
          className={status === "unconfirmed" ? "combobox__input warn" : "combobox__input"}
          value={value}
          placeholder={placeholder}
          onChange={(e) => handleType(e.target.value)}
          onFocus={() => setOpen(true)}
          autoComplete="off"
        />
        {status === "existing" && <span className="combobox__badge ok">✓ vorhanden</span>}
        {status === "new" && value.trim() !== "" && (
          <span className="combobox__badge new">＋ neu</span>
        )}

        {hasDropdown && (
          <div className="combobox__menu" role="listbox">
            {prioFiltered.length > 0 && (
              <div className="combobox__group">
                {priorityLabel && <p className="combobox__group-label">{priorityLabel}</p>}
                {prioFiltered.map((o) => (
                  <button
                    key={`p-${o}`}
                    type="button"
                    className="combobox__option"
                    onMouseDown={(e) => {
                      e.preventDefault();
                      select(o);
                    }}
                  >
                    {o}
                  </button>
                ))}
              </div>
            )}
            {restFiltered.length > 0 && (
              <div className="combobox__group">
                {priorityLabel && restLabel && prioFiltered.length > 0 && (
                  <p className="combobox__group-label">{restLabel}</p>
                )}
                {restFiltered.map((o) => (
                  <button
                    key={`r-${o}`}
                    type="button"
                    className="combobox__option"
                    onMouseDown={(e) => {
                      e.preventDefault();
                      select(o);
                    }}
                  >
                    {o}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {status === "unconfirmed" && (
        <div className="combobox__warn">
          <p className="combobox__warn-text">
            Ähnlich vorhanden — bitte wählen, um Doppel zu vermeiden:
          </p>
          <div className="combobox__suggestions">
            {similar.map((o) => (
              <button
                key={`s-${o}`}
                type="button"
                className="combobox__suggestion"
                onClick={() => select(o)}
              >
                {o}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="combobox__new-btn"
            onClick={() => {
              setConfirmedNew(true);
              setOpen(false);
            }}
          >
            „{value.trim()}" neu anlegen
          </button>
        </div>
      )}
    </div>
  );
}
