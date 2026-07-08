import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api } from "../lib/api.js";

export default function Login() {
  const nav = useNavigate();
  const [tab, setTab] = useState("an"); // "an" = anmelden, "neu" = registrieren
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [grade, setGrade] = useState("2. Oberstufe");
  const [role, setRole] = useState("student");
  const [status, setStatus] = useState(null); // {type, text, url}
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e?.preventDefault();
    if (!email.trim()) return;
    setBusy(true);
    setStatus(null);
    try {
      const body = { email: email.trim(), register: tab === "neu" };
      if (tab === "neu") {
        body.display_name = name.trim() || undefined;
        body.role = role;
        if (role === "student") body.grade_level = grade;
      }
      const res = await api.post("/api/auth/request-link", body);
      if (res.dev_token) {
        // Dev-Modus: kein Mailserver – direkt zum Verify
        setStatus({ type: "dev", text: "Dev-Modus: du wirst direkt eingeloggt …" });
        nav(`/login/verify?token=${encodeURIComponent(res.dev_token)}`);
      } else {
        setStatus({ type: "sent", text: "Wir haben dir einen Login-Link geschickt. Schau in dein E-Mail-Postfach." });
      }
    } catch (err) {
      setStatus({ type: "error", text: err.message });
    } finally {
      setBusy(false);
    }
  }

  const tabStyle = (active) => ({
    flex: 1,
    textAlign: "center",
    fontSize: 13,
    fontWeight: 600,
    borderRadius: 8,
    padding: 8,
    cursor: "pointer",
    background: active ? "#fff" : "transparent",
    color: active ? "#1a1c22" : "#6b7280",
    boxShadow: active ? "0 1px 3px rgba(0,0,0,.08)" : "none",
    border: "none",
  });

  return (
    <div style={{ minHeight: "100vh", display: "flex" }} className="login-split">
      {/* linke Seite (indigo) */}
      <div style={{ flex: "0 0 46%", background: "#4f46e5", color: "#fff", padding: "46px 44px", position: "relative", overflow: "hidden", display: "flex", flexDirection: "column" }} className="login-aside">
        <div style={{ position: "absolute", inset: 0, background: "radial-gradient(560px 320px at 80% 0%, rgba(255,255,255,.16), transparent 70%)" }} />
        <Link to="/" style={{ position: "relative", display: "flex", alignItems: "center", gap: 10, marginBottom: "auto" }}>
          <span style={{ width: 26, height: 26, borderRadius: 8, background: "#fff" }} />
          <span style={{ fontWeight: 800, fontSize: 18, letterSpacing: "-.02em" }}>Schrittweise</span>
        </Link>
        <div style={{ position: "relative" }}>
          <div style={{ fontSize: 30, fontWeight: 800, lineHeight: 1.18, letterSpacing: "-.02em", marginBottom: 22, textWrap: "balance" }}>
            «Endlich versteh ich <span style={{ opacity: 0.7 }}>warum</span> – nicht nur das Resultat.»
          </div>
          <div style={{ background: "rgba(255,255,255,.12)", border: "1px solid rgba(255,255,255,.18)", borderRadius: 16, padding: "16px 18px", display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ alignSelf: "flex-end", background: "#fff", color: "#1a1c22", borderRadius: 14, borderBottomRightRadius: 4, padding: "9px 13px", fontSize: 13, maxWidth: "80%" }}>gib mir die Lösung 🙏</div>
            <div style={{ alignSelf: "flex-start", background: "rgba(255,255,255,.16)", borderRadius: 14, borderBottomLeftRadius: 4, padding: "9px 13px", fontSize: 13, maxWidth: "88%" }}>
              Mach ich extra nicht 🙂 Was müsstest du zuerst mit der +5 machen?
            </div>
          </div>
        </div>
      </div>

      {/* rechte Seite (Formular) */}
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 40 }}>
        <form onSubmit={submit} style={{ width: 340 }}>
          <div style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-.02em", marginBottom: 6 }}>
            {tab === "an" ? "Willkommen zurück" : "Leg in 10 Sekunden los"}
          </div>
          <div style={{ fontSize: 14, color: "#6b7280", marginBottom: 26 }}>Melde dich an oder leg in 10 Sekunden los.</div>

          <div style={{ display: "flex", background: "#f1f2f6", borderRadius: 11, padding: 4, marginBottom: 22 }}>
            <button type="button" onClick={() => setTab("an")} style={tabStyle(tab === "an")}>Anmelden</button>
            <button type="button" onClick={() => setTab("neu")} style={tabStyle(tab === "neu")}>Neu hier</button>
          </div>

          {tab === "neu" && (
            <>
              <label style={{ fontSize: 12, fontWeight: 600, color: "#6b7280", display: "block", marginBottom: 6 }}>Ich bin …</label>
              <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
                {[["student", "👩‍🎓 Schüler:in"], ["parent", "👪 Elternteil"]].map(([val, lbl]) => (
                  <button type="button" key={val} onClick={() => setRole(val)} style={{ flex: 1, fontSize: 13, fontWeight: 600, borderRadius: 10, padding: "9px", cursor: "pointer", background: role === val ? "#eef0fe" : "#fff", color: role === val ? "#4f46e5" : "#6b7280", border: `1px solid ${role === val ? "#c9ccf6" : "#e7e8ee"}` }}>{lbl}</button>
                ))}
              </div>
              <label style={{ fontSize: 12, fontWeight: 600, color: "#6b7280", display: "block", marginBottom: 6 }}>Anzeigename (kein Klarname nötig)</label>
              <div style={{ display: "flex", alignItems: "center", gap: 8, border: "1px solid #d2d4dd", borderRadius: 11, padding: "11px 13px", marginBottom: 14 }}>
                <span style={{ color: "#b6bcc6", fontSize: 14 }}>☺</span>
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder="z.B. Mia" className="input-clean" style={{ flex: 1 }} />
              </div>
            </>
          )}

          <label style={{ fontSize: 12, fontWeight: 600, color: "#6b7280", display: "block", marginBottom: 6 }}>E-Mail</label>
          <div style={{ display: "flex", alignItems: "center", gap: 8, border: "1px solid #d2d4dd", borderRadius: 11, padding: "11px 13px", marginBottom: 14 }}>
            <span style={{ color: "#b6bcc6", fontSize: 14 }}>✉</span>
            <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" placeholder="du@schule.ch" className="input-clean" style={{ flex: 1 }} />
          </div>
          <div style={{ fontSize: 12, color: "#9aa0ab", marginBottom: 16, lineHeight: 1.5 }}>Wir schicken dir einen Link – kein Passwort zum Merken.</div>

          <button type="submit" disabled={busy} className="btn-primary" style={{ width: "100%", borderRadius: 12, padding: 13, fontSize: 15, marginBottom: 18, opacity: busy ? 0.7 : 1 }}>
            {busy ? "einen Moment …" : "Link senden"}
          </button>

          {status && (
            <div
              style={{
                fontSize: 13,
                borderRadius: 10,
                padding: "10px 12px",
                marginBottom: 16,
                background: status.type === "error" ? "#fdecec" : "#eef7f0",
                color: status.type === "error" ? "#c0392b" : "#1a7f3c",
                border: `1px solid ${status.type === "error" ? "#f5cccc" : "#cde7d6"}`,
              }}
            >
              {status.text}
            </div>
          )}

          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 18 }}>
            <span style={{ flex: 1, height: 1, background: "#e7e8ee" }} />
            <span style={{ fontSize: 12, color: "#b6bcc6" }}>oder</span>
            <span style={{ flex: 1, height: 1, background: "#e7e8ee" }} />
          </div>
          <div style={{ border: "1px solid #d2d4dd", borderRadius: 12, padding: 12, textAlign: "center", fontSize: 14, fontWeight: 600, display: "flex", alignItems: "center", justifyContent: "center", gap: 9, opacity: 0.6, cursor: "not-allowed" }} title="Bald verfügbar">
            <span style={{ width: 16, height: 16, borderRadius: "50%", background: "conic-gradient(#ea4335,#fbbc05,#34a853,#4285f4)" }} />
            Weiter mit Google
          </div>
          <div style={{ fontSize: 11, color: "#9aa0ab", textAlign: "center", marginTop: 22, lineHeight: 1.5 }}>
            Daten in der Schweiz · kein Klarname nötig
            <br />
            <Link to="/impressum" style={{ color: "#9aa0ab", textDecoration: "underline" }}>Impressum</Link>
            {" · "}
            <Link to="/datenschutz" style={{ color: "#9aa0ab", textDecoration: "underline" }}>Datenschutz</Link>
          </div>
        </form>
      </div>
    </div>
  );
}
