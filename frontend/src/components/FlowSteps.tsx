import { Icon } from "./Icon";

type Props = {
  /** 1-based index of the step the user should act on next. */
  current: number;
};

const STEPS = [
  { n: 1, label: "Datei" },
  { n: 2, label: "Artikel" },
  { n: 3, label: "Offerte" },
  { n: 4, label: "Export" },
];

// Short, action-oriented hint shown for the active step.
const HINTS: Record<number, string> = {
  1: "Lade eine Lieferanten-Datei hoch (Excel oder CSV).",
  2: "Positionen extrahieren – meist automatisch, sonst „Mit Claude extrahieren“.",
  3: "Marke und Lieferant eintragen und die Marge prüfen.",
  4: "Alles bereit – Offerte als Excel exportieren (Button unten rechts).",
};

export function FlowSteps({ current }: Props) {
  return (
    <nav className="stepper" aria-label="Fortschritt">
      <ol className="stepper-list">
        {STEPS.map((s) => {
          const state = s.n < current ? "done" : s.n === current ? "current" : "todo";
          return (
            <li key={s.n} className={`step step--${state}`}>
              <span className="step-dot">
                {state === "done" ? <Icon name="check" size={15} strokeWidth={3} /> : s.n}
              </span>
              <span className="step-label">{s.label}</span>
            </li>
          );
        })}
      </ol>
      <p className="stepper-hint">{HINTS[current]}</p>
    </nav>
  );
}
