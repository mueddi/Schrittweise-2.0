import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, HashRouter } from "react-router-dom";
import App from "./App.jsx";
import { AuthProvider } from "./lib/auth.jsx";
import { LanguageProvider } from "./lib/i18n.jsx";
import "./styles/theme.css";

// Demo-Build (VITE_DEMO=1): Mock-Backend im Browser + HashRouter (kein Server-Rewrite noetig)
const IS_DEMO = import.meta.env.VITE_DEMO === "1";
const Router = IS_DEMO ? HashRouter : BrowserRouter;

// Auffangnetz: ein JS-Fehler in einem Screen zeigt eine freundliche Meldung
// statt eines weissen Bildschirms.
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.error("Unbehandelter Fehler:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ display: "grid", placeItems: "center", height: "100vh", background: "#fbfbfd", padding: 24, fontFamily: "Inter, system-ui, sans-serif" }}>
          <div style={{ textAlign: "center", maxWidth: 400 }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>😵</div>
            <div style={{ fontSize: 18, fontWeight: 800, marginBottom: 6, color: "#1a1c22" }}>Ups, da ist etwas schiefgelaufen</div>
            <div style={{ fontSize: 14, color: "#6b7280", marginBottom: 20, lineHeight: 1.55 }}>
              Keine Sorge, dein Fortschritt ist gespeichert. Lade die Seite neu – dann geht es weiter.
            </div>
            <button
              onClick={() => window.location.reload()}
              style={{ border: "none", color: "#fff", background: "#6366f1", borderRadius: 12, fontWeight: 600, fontSize: 14, padding: "12px 24px", cursor: "pointer" }}
            >
              Neu laden
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

async function boot() {
  if (IS_DEMO) {
    await import("./lib/mockApi.js");
  }
  ReactDOM.createRoot(document.getElementById("root")).render(
    <React.StrictMode>
      <ErrorBoundary>
        <Router>
          <LanguageProvider>
            <AuthProvider>
              <App />
            </AuthProvider>
          </LanguageProvider>
        </Router>
      </ErrorBoundary>
    </React.StrictMode>
  );
}

boot();
