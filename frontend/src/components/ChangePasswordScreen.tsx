import { useState } from "react";

import { apiChangePassword } from "../api";
import type { AuthUser } from "../types";

type Props = {
  /** When true, the user cannot skip (forced change on first login). */
  forced: boolean;
  onDone: (user: AuthUser) => void;
  onCancel?: () => void;
};

export function ChangePasswordScreen({ forced, onDone, onCancel }: Props) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setError("");
    if (next.length < 8) {
      setError("Neues Passwort muss mindestens 8 Zeichen haben.");
      return;
    }
    if (next !== confirm) {
      setError("Die neuen Passwörter stimmen nicht überein.");
      return;
    }
    setBusy(true);
    try {
      const user = await apiChangePassword(current, next);
      onDone(user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Passwortänderung fehlgeschlagen");
      setBusy(false);
    }
  }

  const card = (
    <form className="login-card" onSubmit={(e) => void handleSubmit(e)}>
      <h1 className="login-title">Passwort ändern</h1>
      <p className="login-sub">
        {forced
          ? "Bitte vergib ein eigenes Passwort, um fortzufahren."
          : "Lege ein neues Passwort fest."}
      </p>

      <label className="login-field">
        <span>Aktuelles Passwort</span>
        <input
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          required
          autoFocus
        />
      </label>

      <label className="login-field">
        <span>Neues Passwort</span>
        <input
          type="password"
          autoComplete="new-password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          required
        />
      </label>

      <label className="login-field">
        <span>Neues Passwort bestätigen</span>
        <input
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
        />
      </label>

      {error && <p className="login-error">{error}</p>}

      <button type="submit" className="login-submit" disabled={busy}>
        {busy ? "Speichern …" : "Passwort speichern"}
      </button>
      {!forced && onCancel && (
        <button type="button" className="login-cancel" onClick={onCancel} disabled={busy}>
          Abbrechen
        </button>
      )}
    </form>
  );

  if (forced) {
    return <main className="login-page">{card}</main>;
  }
  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div onClick={(e) => e.stopPropagation()}>{card}</div>
    </div>
  );
}
