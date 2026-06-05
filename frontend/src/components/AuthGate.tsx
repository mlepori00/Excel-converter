import { useEffect, useState } from "react";

import App from "../App";
import { apiMe, getToken, setAuthErrorHandler, setToken } from "../api";
import type { AuthUser } from "../types";
import { LoginScreen } from "./LoginScreen";

export function AuthGate() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checking, setChecking] = useState(true);

  // Any 401 from the API drops the user back to the login screen.
  useEffect(() => {
    setAuthErrorHandler(() => setUser(null));
    return () => setAuthErrorHandler(null);
  }, []);

  // Validate an existing token on first load.
  useEffect(() => {
    let active = true;
    if (!getToken()) {
      setChecking(false);
      return;
    }
    apiMe()
      .then((u) => {
        if (active) setUser(u);
      })
      .catch(() => {
        /* invalid/expired token – handleUnauthorized already cleared it */
      })
      .finally(() => {
        if (active) setChecking(false);
      });
    return () => {
      active = false;
    };
  }, []);

  function handleLogout() {
    setToken(null);
    setUser(null);
  }

  if (checking) {
    return (
      <main className="login-page">
        <p className="login-loading">Lädt …</p>
      </main>
    );
  }
  if (!user) {
    return <LoginScreen onLogin={setUser} />;
  }
  return <App user={user} onLogout={handleLogout} />;
}
