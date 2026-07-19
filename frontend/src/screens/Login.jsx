import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";
import { useLang, GRADE_KEYS, gradeLabel } from "../lib/i18n.jsx";

export default function Login() {
  const nav = useNavigate();
  const { login } = useAuth();
  const { t, lang, setLang } = useLang();
  const [tab, setTab] = useState("an"); // "an" = anmelden, "neu" = registrieren
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [grade, setGrade] = useState(""); // bewusst leer: Stufe aktiv wählen
  const [role, setRole] = useState("student");
  const [terms, setTerms] = useState(false);
  const [website, setWebsite] = useState(""); // Honeypot – bleibt bei Menschen leer
  const [status, setStatus] = useState(null); // {type, text}
  const [busy, setBusy] = useState(false);

  async function forgotPassword() {
    if (!email.trim()) {
      setStatus({ type: "error", text: t("Gib zuerst deine E-Mail ein, dann klick auf «Passwort vergessen».", "Enter your email first, then click “Forgot password”.") });
      return;
    }
    setBusy(true);
    setStatus(null);
    try {
      await api.post("/api/auth/request-link", { email: email.trim() });
      setStatus({
        type: "ok",
        text: t(
          "Wir haben dir einen Anmelde-Link geschickt. Nach dem Klick bist du drin und kannst in den Einstellungen ein neues Passwort setzen.",
          "We've sent you a sign-in link. After clicking it you're in and can set a new password in the settings."
        ),
      });
    } catch (err) {
      setStatus({ type: "error", text: err.message });
    } finally {
      setBusy(false);
    }
  }

  async function submit(e) {
    e?.preventDefault();
    if (!email.trim() || !password) return;
    if (tab === "neu" && password.length < 8) {
      setStatus({ type: "error", text: t("Das Passwort braucht mindestens 8 Zeichen.", "The password needs at least 8 characters.") });
      return;
    }
    if (tab === "neu" && role === "student" && !grade) {
      setStatus({ type: "error", text: t("Bitte wähle deine Stufe aus.", "Please choose your level.") });
      return;
    }
    if (tab === "neu" && !terms) {
      setStatus({ type: "error", text: t("Bitte akzeptiere zuerst die AGB und die Datenschutzerklärung.", "Please accept the terms of service and the privacy policy first.") });
      return;
    }
    setBusy(true);
    setStatus(null);
    try {
      let res;
      if (tab === "neu") {
        const body = { email: email.trim(), password, role, terms_accepted: terms, website, language: lang };
        if (name.trim()) body.display_name = name.trim();
        if (role === "student") body.grade_level = grade;
        res = await api.post("/api/auth/register", body);
      } else {
        res = await api.post("/api/auth/login", { email: email.trim(), password });
      }
      await login(res.access_token, res.user);
      nav(res.user.role === "parent" ? "/eltern" : "/app/lernen", { replace: true });
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

  const langBtn = (l) => ({
    border: "none",
    background: "transparent",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    color: lang === l ? "#4f46e5" : "#9aa0ab",
    padding: "2px 4px",
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
            {lang === "en"
              ? <>“Finally I get <span style={{ opacity: 0.7 }}>why</span> – not just the result.”</>
              : <>«Endlich versteh ich <span style={{ opacity: 0.7 }}>warum</span> – nicht nur das Resultat.»</>}
          </div>
          <div style={{ background: "rgba(255,255,255,.12)", border: "1px solid rgba(255,255,255,.18)", borderRadius: 16, padding: "16px 18px", display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ alignSelf: "flex-end", background: "#fff", color: "#1a1c22", borderRadius: 14, borderBottomRightRadius: 4, padding: "9px 13px", fontSize: 13, maxWidth: "80%" }}>{t("gib mir die Lösung 🙏", "just give me the answer 🙏")}</div>
            <div style={{ alignSelf: "flex-start", background: "rgba(255,255,255,.16)", borderRadius: 14, borderBottomLeftRadius: 4, padding: "9px 13px", fontSize: 13, maxWidth: "88%" }}>
              {t("Mach ich extra nicht 🙂 Was müsstest du zuerst mit der +5 machen?", "I won't do that on purpose 🙂 What would you do first with the +5?")}
            </div>
          </div>
        </div>
      </div>

      {/* rechte Seite (Formular) */}
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 40, position: "relative" }}>
        <div style={{ position: "absolute", top: 18, right: 22, display: "flex", alignItems: "center", gap: 2 }}>
          <button type="button" onClick={() => setLang("de")} style={langBtn("de")}>DE</button>
          <span style={{ color: "#d2d4dd", fontSize: 12 }}>|</span>
          <button type="button" onClick={() => setLang("en")} style={langBtn("en")}>EN</button>
        </div>
        <form onSubmit={submit} style={{ width: 340 }}>
          <div style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-.02em", marginBottom: 6 }}>
            {tab === "an" ? t("Willkommen zurück", "Welcome back") : t("Leg in 10 Sekunden los", "Get started in 10 seconds")}
          </div>
          <div style={{ fontSize: 14, color: "#6b7280", marginBottom: 26 }}>
            {tab === "an" ? t("Schön, dass du wieder da bist.", "Great to see you again.") : t("Nur E-Mail und Passwort – mehr braucht es nicht.", "Just email and password – that's all it takes.")}
          </div>

          <div style={{ display: "flex", background: "#f1f2f6", borderRadius: 11, padding: 4, marginBottom: 22 }}>
            <button type="button" onClick={() => setTab("an")} style={tabStyle(tab === "an")}>{t("Anmelden", "Sign in")}</button>
            <button type="button" onClick={() => setTab("neu")} style={tabStyle(tab === "neu")}>{t("Neu hier", "New here")}</button>
          </div>

          {tab === "neu" && (
            <>
              <label style={{ fontSize: 12, fontWeight: 600, color: "#6b7280", display: "block", marginBottom: 6 }}>{t("Ich bin …", "I am …")}</label>
              <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
                {[["student", t("👩‍🎓 Schüler:in", "👩‍🎓 Student")], ["parent", t("👪 Elternteil", "👪 Parent")]].map(([val, lbl]) => (
                  <button type="button" key={val} onClick={() => setRole(val)} style={{ flex: 1, fontSize: 13, fontWeight: 600, borderRadius: 10, padding: "9px", cursor: "pointer", background: role === val ? "#eef0fe" : "#fff", color: role === val ? "#4f46e5" : "#6b7280", border: `1px solid ${role === val ? "#c9ccf6" : "#e7e8ee"}` }}>{lbl}</button>
                ))}
              </div>
              <label style={{ fontSize: 12, fontWeight: 600, color: "#6b7280", display: "block", marginBottom: 6 }}>{t("Anzeigename (kein Klarname nötig)", "Display name (no real name needed)")}</label>
              <div style={{ display: "flex", alignItems: "center", gap: 8, border: "1px solid #d2d4dd", borderRadius: 11, padding: "11px 13px", marginBottom: 14 }}>
                <span style={{ color: "#b6bcc6", fontSize: 14 }}>☺</span>
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("z.B. Mia", "e.g. Mia")} className="input-clean" style={{ flex: 1 }} />
              </div>
              {role === "student" && (
                <>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "#6b7280", display: "block", marginBottom: 6 }}>{t("Auf welcher Stufe bist du?", "What level are you at?")}</label>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 14 }}>
                    {GRADE_KEYS.map((g) => (
                      <button
                        type="button"
                        key={g}
                        onClick={() => setGrade(g)}
                        style={{ fontSize: 13, fontWeight: 600, borderRadius: 10, padding: "10px 12px", cursor: "pointer", textAlign: "left", background: grade === g ? "#eef0fe" : "#fff", color: grade === g ? "#4f46e5" : "#6b7280", border: `1px solid ${grade === g ? "#c9ccf6" : "#e7e8ee"}` }}
                      >
                        {gradeLabel(g, lang)}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </>
          )}

          <label style={{ fontSize: 12, fontWeight: 600, color: "#6b7280", display: "block", marginBottom: 6 }}>{t("E-Mail", "Email")}</label>
          <div style={{ display: "flex", alignItems: "center", gap: 8, border: "1px solid #d2d4dd", borderRadius: 11, padding: "11px 13px", marginBottom: 14 }}>
            <span style={{ color: "#b6bcc6", fontSize: 14 }}>✉</span>
            <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" placeholder={t("du@schule.ch", "you@school.com")} className="input-clean" style={{ flex: 1 }} />
          </div>

          <label style={{ fontSize: 12, fontWeight: 600, color: "#6b7280", display: "block", marginBottom: 6 }}>{t("Passwort", "Password")}</label>
          <div style={{ display: "flex", alignItems: "center", gap: 8, border: "1px solid #d2d4dd", borderRadius: 11, padding: "11px 13px", marginBottom: 14 }}>
            <span style={{ color: "#b6bcc6", fontSize: 14 }}>🔒</span>
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              placeholder={tab === "neu" ? t("mindestens 8 Zeichen", "at least 8 characters") : t("dein Passwort", "your password")}
              autoComplete={tab === "neu" ? "new-password" : "current-password"}
              className="input-clean"
              style={{ flex: 1 }}
            />
          </div>
          {tab === "neu" && (
            <>
              <div style={{ fontSize: 12, color: "#9aa0ab", marginBottom: 12, lineHeight: 1.5 }}>{t("Merk dir dein Passwort gut – Tipp: drei Wörter, die du dir vorstellen kannst.", "Remember your password well – tip: three words you can picture.")}</div>
              {/* Honeypot: fuer Menschen unsichtbar, simple Bots fuellen es aus */}
              <input
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
                name="website"
                tabIndex={-1}
                autoComplete="off"
                aria-hidden="true"
                style={{ position: "absolute", left: "-9999px", width: 1, height: 1, opacity: 0 }}
              />
              <label style={{ display: "flex", gap: 9, alignItems: "flex-start", fontSize: 12, color: "#6b7280", marginBottom: 8, cursor: "pointer", lineHeight: 1.5 }}>
                <input type="checkbox" checked={terms} onChange={(e) => setTerms(e.target.checked)} style={{ marginTop: 2 }} />
                <span>
                  {t("Ich akzeptiere die ", "I accept the ")}<Link to="/agb" target="_blank" style={{ color: "#4f46e5", textDecoration: "underline" }}>{t("AGB", "Terms of Service")}</Link>{t(" und die ", " and the ")}
                  <Link to="/datenschutz" target="_blank" style={{ color: "#4f46e5", textDecoration: "underline" }}>{t("Datenschutzerklärung", "Privacy Policy")}</Link>.
                </span>
              </label>
              <div style={{ fontSize: 11, color: "#9aa0ab", marginBottom: 16 }}>{t("Unter 16? Frag zuerst deine Eltern, ob das okay ist.", "Under 16? Ask your parents first if that's okay.")}</div>
            </>
          )}
          {tab === "an" && (
            <div style={{ textAlign: "right", marginBottom: 16 }}>
              <button type="button" onClick={forgotPassword} disabled={busy} style={{ border: "none", background: "transparent", fontSize: 12, color: "#4f46e5", fontWeight: 600, cursor: "pointer", padding: 0 }}>
                {t("Passwort vergessen?", "Forgot password?")}
              </button>
            </div>
          )}

          <button type="submit" disabled={busy} className="btn-primary" style={{ width: "100%", borderRadius: 12, padding: 13, fontSize: 15, marginBottom: 18, opacity: busy ? 0.7 : 1 }}>
            {busy ? t("einen Moment …", "one moment …") : tab === "neu" ? t("Konto erstellen", "Create account") : t("Anmelden", "Sign in")}
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

          <div style={{ fontSize: 11, color: "#9aa0ab", textAlign: "center", marginTop: 22, lineHeight: 1.5 }}>
            {t("Verschlüsselte Übertragung · kein Klarname nötig", "Encrypted connection · no real name needed")}
            <br />
            <Link to="/impressum" style={{ color: "#9aa0ab", textDecoration: "underline" }}>{t("Impressum", "Legal notice")}</Link>
            {" · "}
            <Link to="/datenschutz" style={{ color: "#9aa0ab", textDecoration: "underline" }}>{t("Datenschutz", "Privacy")}</Link>
            {" · "}
            <Link to="/agb" style={{ color: "#9aa0ab", textDecoration: "underline" }}>{t("AGB", "Terms")}</Link>
          </div>
        </form>
      </div>
    </div>
  );
}
