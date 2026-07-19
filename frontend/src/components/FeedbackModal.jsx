import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";
import { useLang } from "../lib/i18n.jsx";

// Feedback-Fenster: alle Eingeloggten koennen senden (wird in der DB
// gespeichert); das Admin-Konto sieht zusaetzlich alle Eingaenge.
export default function FeedbackModal({ onClose }) {
  const { user } = useAuth();
  const { t } = useLang();
  const loc = useLocation();
  const [tab, setTab] = useState("senden"); // "senden" | "eingegangen" (nur Admin)
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState(null);
  const [items, setItems] = useState(null); // Admin-Liste

  useEffect(() => {
    if (tab === "eingegangen" && user?.is_admin) {
      api.get("/api/feedback").then(setItems).catch(() => setItems([]));
    }
  }, [tab, user]);

  async function send() {
    if (text.trim().length < 3 || busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/feedback", { text: text.trim(), page: loc.pathname.slice(0, 80) });
      setSent(true);
      setText("");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(20,22,30,.45)", zIndex: 60, display: "grid", placeItems: "center", padding: 14 }}>
      <div onClick={(e) => e.stopPropagation()} className="popin" style={{ background: "#fff", borderRadius: 18, width: "min(560px, 100%)", maxHeight: "86vh", display: "flex", flexDirection: "column", overflow: "hidden", boxShadow: "0 20px 60px rgba(20,22,30,.25)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 18px", borderBottom: "1px solid #eef0f3" }}>
          <div style={{ fontSize: 15, fontWeight: 800 }}>💬 Feedback</div>
          <button onClick={onClose} style={{ border: "none", background: "transparent", fontSize: 18, color: "#9aa0ab", cursor: "pointer" }}>✕</button>
        </div>

        {user?.is_admin && (
          <div style={{ display: "flex", gap: 6, padding: "10px 18px 0" }}>
            {[["senden", t("Senden", "Send")], ["eingegangen", t("Eingegangen", "Inbox")]].map(([k, label]) => (
              <button key={k} onClick={() => setTab(k)} style={{ border: "none", borderRadius: 999, padding: "7px 14px", fontSize: 12.5, fontWeight: 600, cursor: "pointer", background: tab === k ? "#eef0fe" : "#f6f7fb", color: tab === k ? "#4f46e5" : "#6b7280" }}>
                {label}
              </button>
            ))}
          </div>
        )}

        {tab === "senden" && (
          <div style={{ padding: 18 }}>
            {sent ? (
              <div style={{ textAlign: "center", padding: "18px 0" }}>
                <div style={{ fontSize: 30, marginBottom: 8 }}>🙏</div>
                <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>{t("Danke für dein Feedback!", "Thanks for your feedback!")}</div>
                <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 16 }}>{t("Es hilft uns, Schrittweise besser zu machen.", "It helps us make Schrittweise better.")}</div>
                <button onClick={onClose} className="btn-primary" style={{ padding: "10px 20px", borderRadius: 10, fontSize: 13, border: "none" }}>{t("Schliessen", "Close")}</button>
              </div>
            ) : (
              <>
                <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 10 }}>
                  {t("Was gefällt dir? Was nervt? Was fehlt? Schreib es uns – wir lesen alles.", "What do you like? What's annoying? What's missing? Tell us – we read everything.")}
                </div>
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  rows={5}
                  maxLength={2000}
                  placeholder={t("Dein Feedback …", "Your feedback …")}
                  autoFocus
                  style={{ width: "100%", border: "1px solid #d2d4dd", borderRadius: 12, padding: "11px 13px", fontSize: 14, resize: "vertical", outline: "none", marginBottom: 10 }}
                />
                {error && <div style={{ fontSize: 13, color: "#c0392b", marginBottom: 10 }}>{error}</div>}
                <button onClick={send} disabled={busy || text.trim().length < 3} className="btn-primary" style={{ width: "100%", borderRadius: 11, padding: 12, fontSize: 14, border: "none", opacity: busy || text.trim().length < 3 ? 0.6 : 1 }}>
                  {busy ? t("sendet …", "sending …") : t("Feedback senden", "Send feedback")}
                </button>
              </>
            )}
          </div>
        )}

        {tab === "eingegangen" && (
          <div style={{ padding: 18, overflowY: "auto" }}>
            {items === null && <div style={{ fontSize: 13, color: "#9aa0ab" }}>{t("lädt …", "loading …")}</div>}
            {items?.length === 0 && <div style={{ fontSize: 13, color: "#9aa0ab" }}>{t("Noch kein Feedback eingegangen.", "No feedback received yet.")}</div>}
            {items?.map((f) => (
              <div key={f.id} style={{ borderTop: "1px solid #f4f5f8", padding: "12px 0" }}>
                <div style={{ fontSize: 11.5, color: "#9aa0ab", marginBottom: 4 }}>
                  {new Date(f.created_at).toLocaleString("de-CH")} · {f.display_name} ({f.role}){f.page ? ` · ${f.page}` : ""}
                </div>
                <div style={{ fontSize: 13.5, lineHeight: 1.55, whiteSpace: "pre-wrap" }}>{f.text}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
