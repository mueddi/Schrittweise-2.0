// Schmaler API-Client. Basis-URL aus VITE_API_BASE (leer = Vite-Dev-Proxy).
const BASE = import.meta.env.VITE_API_BASE || "";

let token = localStorage.getItem("sw_token") || null;

export function setToken(t) {
  token = t;
  if (t) localStorage.setItem("sw_token", t);
  else localStorage.removeItem("sw_token");
}
export function getToken() {
  return token;
}

let onUnauthorized = null;
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

function headers(extra = {}) {
  const h = { "Content-Type": "application/json", ...extra };
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

async function handle(res) {
  if (res.status === 401) {
    setToken(null);
    onUnauthorized?.();
    throw new Error("Sitzung abgelaufen – bitte neu anmelden.");
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data?.detail || data?.message || `Fehler ${res.status}`;
    throw new Error(typeof msg === "string" ? msg : "Unbekannter Fehler");
  }
  return data;
}

export const api = {
  base: BASE,
  get: (path) => fetch(`${BASE}${path}`, { headers: headers() }).then(handle),
  post: (path, body) =>
    fetch(`${BASE}${path}`, { method: "POST", headers: headers(), body: JSON.stringify(body || {}) }).then(handle),
  patch: (path, body) =>
    fetch(`${BASE}${path}`, { method: "PATCH", headers: headers(), body: JSON.stringify(body || {}) }).then(handle),
  del: (path) => fetch(`${BASE}${path}`, { method: "DELETE", headers: headers() }).then(handle),
  // multipart-Upload (Foto)
  upload: (path, formData) =>
    fetch(`${BASE}${path}`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    }).then(handle),
  // Streaming (SSE-artig, zeilenweise) fuer den Tutor-Chat
  stream: (path, body) =>
    fetch(`${BASE}${path}`, { method: "POST", headers: headers(), body: JSON.stringify(body || {}) }),
};
