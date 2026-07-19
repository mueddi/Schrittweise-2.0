import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";
import { useLang, gradeLabel } from "../lib/i18n.jsx";
import { ChildDashboard } from "./Eltern.jsx";
import { DeleteAccount, PasswordTab } from "./Einstellungen.jsx";

// Eigenständige Eltern-Ansicht (Rolle parent). Kein Schüler-Sidebar.
// preview: Admin-Vorschau – zeigt dieselbe Ansicht mit den EIGENEN
// Übungsdaten (GET /api/parents/preview), zum Testen der Eltern-Sicht.
export default function ParentDashboard({ preview = false }) {
  const { user, logout } = useAuth();
  const { t, lang } = useLang();
  const [children, setChildren] = useState([]);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [active, setActive] = useState(0);
  const [kontoOpen, setKontoOpen] = useState(false);

  const load = () => (preview
    ? api.get("/api/parents/preview").then((d) => setChildren([d]))
    : api.get("/api/parents/children").then(setChildren)
  ).catch(() => setChildren([]));
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function redeem(e) {
    e?.preventDefault();
    if (!code.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/parents/redeem", { invite_code: code.trim() });
      setCode("");
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const child = children[active];

  return (
    <div style={{ minHeight: "100vh", background: "#fbfbfd" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 28px", borderBottom: "1px solid #eef0f3", background: "#fff" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <span style={{ width: 22, height: 22, borderRadius: 7, background: "#6366f1" }} />
          <span style={{ fontWeight: 800, fontSize: 16, color: "#4f46e5", letterSpacing: "-.02em" }}>Schrittweise</span>
          <span style={{ fontSize: 12, fontWeight: 600, color: "#6b7280", background: "#f1f2f6", borderRadius: 999, padding: "4px 12px", marginLeft: 8 }}>{t("Elternansicht", "Parent view")}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <span style={{ fontSize: 13, color: "#6b7280" }}>{user?.display_name}</span>
          {preview ? (
            <Link to="/app/lernen" style={{ fontSize: 12, fontWeight: 600, color: "#4f46e5" }}>{t("← Zurück zur App", "← Back to the app")}</Link>
          ) : (
            <>
              <span onClick={() => setKontoOpen(!kontoOpen)} style={{ fontSize: 12, fontWeight: 600, color: kontoOpen ? "#1a1c22" : "#4f46e5", cursor: "pointer" }}>⚙ {t("Konto", "Account")}</span>
              <span onClick={logout} style={{ fontSize: 12, fontWeight: 600, color: "#4f46e5", cursor: "pointer" }}>{t("Abmelden", "Log out")}</span>
            </>
          )}
        </div>
      </div>

      {preview && (
        <div style={{ background: "#fdf3e6", borderBottom: "1px solid #f2ddb8", padding: "8px 28px", fontSize: 12.5, color: "#a05c12" }}>
          {t("👁 Vorschau: So sehen Eltern die Ansicht – gezeigt werden deine eigenen Übungsdaten.",
             "👁 Preview: this is what parents see – showing your own practice data.")}
        </div>
      )}

      <div style={{ maxWidth: 1000, margin: "0 auto", padding: "24px 28px" }}>
        {children.length > 1 && (
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            {children.map((k, i) => (
              <span key={i} onClick={() => setActive(i)} style={{ cursor: "pointer", fontSize: 13, fontWeight: 600, color: i === active ? "#4f46e5" : "#6b7280", background: i === active ? "#eef0fe" : "#fff", border: i === active ? "none" : "1px solid #e7e8ee", borderRadius: 999, padding: "7px 14px" }}>{k.student_display_name}</span>
            ))}
          </div>
        )}

        {child ? (
          <>
            <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 8 }}>
              <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-.02em" }}>{child.student_display_name} · {gradeLabel(child.grade_level, lang)}</div>
            </div>
            {child.shared ? (
              <ChildDashboard data={child} />
            ) : (
              <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, padding: 24, color: "#6b7280", fontSize: 14 }}>
                {child.student_display_name} {t("hat die Fortschritts-Freigabe (noch) nicht aktiviert. Du siehst Aggregate, sobald die Freigabe an ist.", "has not (yet) enabled progress sharing. You will see aggregated progress as soon as sharing is turned on.")}
              </div>
            )}
          </>
        ) : (
          <div style={{ textAlign: "center", maxWidth: 460, margin: "60px auto 0" }}>
            <div style={{ width: 64, height: 64, borderRadius: 18, background: "#eef0fe", color: "#4f46e5", fontSize: 28, display: "grid", placeItems: "center", margin: "0 auto 16px" }}>👪</div>
            <div style={{ fontSize: 18, fontWeight: 800, marginBottom: 6 }}>{t("Kind verknüpfen", "Link your child")}</div>
            <div style={{ fontSize: 14, color: "#6b7280", marginBottom: 20 }}>{t("Gib den Einladungscode ein, den dein Kind dir aus der App gegeben hat. Du siehst nur den groben Fortschritt – nie einzelne Nachrichten.", "Enter the invite code your child gave you from the app. You only see high-level progress – never individual messages.")}</div>
          </div>
        )}

        {!preview && (
        <form onSubmit={redeem} style={{ display: "flex", gap: 10, marginTop: 24, maxWidth: 420 }}>
          <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder={t("Einladungscode, z.B. 8ZEWHBZT", "Invite code, e.g. 8ZEWHBZT")} style={{ flex: 1, border: "1px solid #d2d4dd", borderRadius: 11, padding: "11px 13px", fontSize: 14, outline: "none", letterSpacing: ".1em", fontFamily: "ui-monospace, monospace" }} />
          <button type="submit" disabled={busy} className="btn-primary" style={{ padding: "11px 20px", borderRadius: 11, fontSize: 14, border: "none" }}>{busy ? "…" : t("Verknüpfen", "Link")}</button>
        </form>
        )}
        {error && <div style={{ fontSize: 13, color: "#c0392b", marginTop: 10 }}>{error}</div>}

        {kontoOpen && (
          <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, padding: 24, marginTop: 28, maxWidth: 620 }}>
            <PasswordTab />
            <DeleteAccount />
          </div>
        )}

        <div style={{ fontSize: 11, color: "#9aa0ab", textAlign: "center", margin: "48px 0 24px" }}>
          <Link to="/impressum" style={{ color: "#9aa0ab", textDecoration: "underline" }}>{t("Impressum", "Legal notice")}</Link>
          {" · "}
          <Link to="/datenschutz" style={{ color: "#9aa0ab", textDecoration: "underline" }}>{t("Datenschutz", "Privacy")}</Link>
          {" · "}
          <Link to="/agb" style={{ color: "#9aa0ab", textDecoration: "underline" }}>{t("AGB", "Terms")}</Link>
        </div>
      </div>
    </div>
  );
}
