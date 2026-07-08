import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, HashRouter } from "react-router-dom";
import App from "./App.jsx";
import { AuthProvider } from "./lib/auth.jsx";
import "./styles/theme.css";

// Demo-Build (VITE_DEMO=1): Mock-Backend im Browser + HashRouter (kein Server-Rewrite noetig)
const IS_DEMO = import.meta.env.VITE_DEMO === "1";
const Router = IS_DEMO ? HashRouter : BrowserRouter;

async function boot() {
  if (IS_DEMO) {
    await import("./lib/mockApi.js");
  }
  ReactDOM.createRoot(document.getElementById("root")).render(
    <React.StrictMode>
      <Router>
        <AuthProvider>
          <App />
        </AuthProvider>
      </Router>
    </React.StrictMode>
  );
}

boot();
