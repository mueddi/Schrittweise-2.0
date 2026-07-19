import { Link, useNavigate } from "react-router-dom";
import { useLang } from "../lib/i18n.jsx";

function Badge({ children }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 13.5, color: "#6b7280" }}>
      <span style={{ color: "#1a7f3c", fontWeight: 700 }}>✓</span>
      {children}
    </span>
  );
}

function Dot({ filled }) {
  return (
    <span
      style={{
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: filled ? "#4f46e5" : "#fff",
        border: filled ? "none" : "1.5px solid #c9ccf6",
      }}
    />
  );
}

export default function Landing() {
  const nav = useNavigate();
  const { t, lang, setLang } = useLang();

  const langBtn = (l) => ({
    border: "none",
    background: "transparent",
    fontSize: 13,
    fontWeight: 700,
    cursor: "pointer",
    color: lang === l ? "#4f46e5" : "#9aa0ab",
    padding: "2px 4px",
  });

  return (
    <div style={{ minHeight: "100vh", background: "#fff", overflowX: "hidden" }}>
      <nav style={{ display: "flex", alignItems: "center", gap: 24, padding: "20px 40px", maxWidth: 1180, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ width: 26, height: 26, borderRadius: 8, background: "#6366f1" }} />
          <span style={{ fontWeight: 800, fontSize: 19, color: "#4f46e5", letterSpacing: "-.02em" }}>Schrittweise</span>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 14 }}>
          <span>
            <button onClick={() => setLang("de")} style={langBtn("de")}>DE</button>
            <span style={{ color: "#d2d4dd", fontSize: 13 }}>|</span>
            <button onClick={() => setLang("en")} style={langBtn("en")}>EN</button>
          </span>
          <Link to="/login" style={{ fontSize: 14, fontWeight: 600, border: "1px solid #d2d4dd", borderRadius: 11, padding: "9px 18px" }}>{t("Anmelden", "Sign in")}</Link>
        </div>
      </nav>

      <div
        style={{
          position: "relative",
          maxWidth: 1180,
          margin: "0 auto",
          padding: "36px 40px 64px",
          display: "grid",
          gridTemplateColumns: "1.05fr .95fr",
          gap: 52,
          alignItems: "center",
        }}
        className="landing-hero"
      >
        <div style={{ position: "absolute", inset: 0, background: "radial-gradient(1000px 480px at 78% -10%, #eef0fe, transparent 70%)", pointerEvents: "none" }} />
        <div style={{ position: "relative", zIndex: 1 }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 600, color: "#4f46e5", background: "#eef0fe", borderRadius: 999, padding: "7px 14px", marginBottom: 22 }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#6366f1" }} />
            {t("Mathe-Tutor · Mittelstufe, Oberstufe & Gymnasium", "Math tutor · middle school, secondary school & high school")}
          </div>
          <h1 style={{ margin: "0 0 18px", fontSize: 54, lineHeight: 1.03, fontWeight: 900, letterSpacing: "-.035em", textWrap: "balance" }}>
            {t("Mathe verstehen. Nicht abschreiben.", "Understand math. Don't just copy answers.")}
          </h1>
          <p style={{ margin: "0 0 28px", fontSize: 18, lineHeight: 1.55, color: "#4b5563", maxWidth: "46ch" }}>
            {t("Dein Mathe-Tutor für Mittelstufe, Oberstufe und Gymnasium, der dir die Lösung nie einfach verrät – sondern dich Schritt für Schritt selber draufkommen lässt.",
               "Your math tutor for middle school, secondary school and high school that never just tells you the answer – it helps you figure it out yourself, step by step.")}
          </p>
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 24, flexWrap: "wrap" }}>
            <button onClick={() => nav("/login")} className="btn-primary" style={{ fontSize: 16, padding: "15px 26px", borderRadius: 13 }}>
              {t("Kostenlos loslegen", "Start for free")}
            </button>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 18 }}>
            <Badge>{t("Lehrplan 21 & Matura-Stoff", "Curriculum-aligned up to final exams")}</Badge>
            <Badge>{t("Verrät die Lösung nie direkt", "Never gives away the answer")}</Badge>
            <Badge>{t("Kein Klarname nötig", "No real name needed")}</Badge>
          </div>
        </div>

        {/* Chat-Vorschau mit Hinweis-Leiter */}
        <div style={{ position: "relative", zIndex: 1 }}>
          <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 22, boxShadow: "0 2px 6px rgba(40,40,90,.06),0 30px 60px rgba(40,40,90,.16)", overflow: "hidden" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "15px 18px", borderBottom: "1px solid #eef0f3" }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700 }}>{t("Lineare Gleichungen", "Linear equations")}</div>
                <div style={{ fontSize: 11.5, color: "#9aa0ab" }}>{t("Aufgabe 3 von 8", "Task 3 of 8")}</div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 9, background: "#eef0fe", borderRadius: 999, padding: "6px 12px" }}>
                <span style={{ fontSize: 10.5, fontWeight: 700, color: "#4f46e5" }}>{t("HILFE", "HELP")}</span>
                <span style={{ display: "flex", gap: 4 }}>
                  <Dot filled /><Dot filled /><Dot /><Dot />
                </span>
              </div>
            </div>
            <div style={{ background: "#f6f7fb", padding: 20, display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ alignSelf: "flex-start", background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, borderBottomLeftRadius: 5, boxShadow: "0 6px 16px rgba(40,40,90,.06)", padding: "11px 15px", fontSize: 13.5 }}>
                {t("Löse nach x auf:", "Solve for x:")}
                <span style={{ fontFamily: "Georgia,serif", fontStyle: "italic", fontSize: 18, display: "inline-block", marginTop: 5 }}>3x + 5 = 20</span>
              </div>
              <div style={{ alignSelf: "flex-end", background: "#6366f1", color: "#fff", borderRadius: 16, borderBottomRightRadius: 5, padding: "10px 15px", fontSize: 13.5, maxWidth: "84%" }}>
                {t("ich weiss nicht wie ich anfangen soll", "i don't know how to start")}
              </div>
              <div style={{ alignSelf: "flex-start", background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, borderBottomLeftRadius: 5, boxShadow: "0 6px 16px rgba(40,40,90,.06)", padding: "11px 15px", fontSize: 13.5 }}>
                {lang === "en"
                  ? <>No stress 🙂 What would you have to do so the <b>+5</b> on the left side disappears?</>
                  : <>Kein Stress 🙂 Was müsstest du tun, damit die <b>+5</b> auf der linken Seite verschwindet?</>}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Für Eltern: Fortschritt ja, Chats nein */}
      <div style={{ background: "#fbfbfd", borderTop: "1px solid #eef0f3" }}>
        <div
          style={{
            maxWidth: 1180,
            margin: "0 auto",
            padding: "56px 40px 64px",
            display: "grid",
            gridTemplateColumns: ".95fr 1.05fr",
            gap: 52,
            alignItems: "center",
          }}
          className="landing-hero"
        >
          {/* Mini-Vorschau der Eltern-Ansicht */}
          <div>
            <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 22, boxShadow: "0 2px 6px rgba(40,40,90,.06),0 26px 54px rgba(40,40,90,.13)", overflow: "hidden" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "15px 18px", borderBottom: "1px solid #eef0f3" }}>
                <span style={{ fontSize: 16 }}>👪</span>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700 }}>{t("Elternansicht", "Parent view")}</div>
                  <div style={{ fontSize: 11.5, color: "#9aa0ab" }}>{t("Mia · Oberstufe · diese Woche", "Mia · secondary school · this week")}</div>
                </div>
              </div>
              <div style={{ padding: 18 }}>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 14 }}>
                  {[["78 %", t("Selbständigkeit", "Independence")], ["12", t("Aufgaben gelöst", "Tasks solved")], ["4", t("Tage aktiv", "Days active")]].map(([v, l]) => (
                    <div key={l} style={{ background: "#f8f8ff", border: "1px solid #e0e2fb", borderRadius: 12, padding: "12px 10px", textAlign: "center" }}>
                      <div style={{ fontSize: 20, fontWeight: 800, color: "#4f46e5", letterSpacing: "-.02em" }}>{v}</div>
                      <div style={{ fontSize: 10.5, color: "#6b7280" }}>{l}</div>
                    </div>
                  ))}
                </div>
                <div style={{ fontSize: 13, color: "#4b5563", background: "#f6f7fb", borderRadius: 10, padding: "10px 13px", marginBottom: 12 }}>
                  {t("Algebra läuft gut · Brüche braucht noch Übung", "Algebra is going well · fractions need more practice")}
                </div>
                <div style={{ fontSize: 12, color: "#9aa0ab", display: "flex", alignItems: "center", gap: 7 }}>
                  <span>🔒</span> {t("Chats sind für Eltern nicht einsehbar", "Chats are not visible to parents")}
                </div>
              </div>
            </div>
          </div>

          {/* Erklärtext */}
          <div>
            <div style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 600, color: "#4f46e5", background: "#eef0fe", borderRadius: 999, padding: "7px 14px", marginBottom: 18 }}>
              {t("👪 Für Eltern", "👪 For parents")}
            </div>
            <h2 style={{ margin: "0 0 16px", fontSize: 36, lineHeight: 1.12, fontWeight: 900, letterSpacing: "-.03em", textWrap: "balance" }}>
              {t("Eltern sehen den Fortschritt – nie die Chats.", "Parents see the progress – never the chats.")}
            </h2>
            <p style={{ margin: "0 0 24px", fontSize: 16.5, lineHeight: 1.6, color: "#4b5563", maxWidth: "50ch" }}>
              {t("Dein Kind gibt dir aus der App einen Einladungscode. Damit erstellst du dein eigenes Eltern-Konto und siehst jede Woche auf einen Blick, wie das Üben läuft – was gut sitzt, wo es noch harzt und wie selbständig gearbeitet wird.",
                 "Your child gives you an invitation code from the app. With it you create your own parent account and see at a glance every week how practice is going – what's solid, where it's still tricky, and how independently they work.")}
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <Badge>{t("Eigenes Eltern-Konto", "Your own parent account")}</Badge>
              <Badge>{t("Verknüpfen per Code vom Kind", "Linked via a code from your child")}</Badge>
              <Badge>{t("Nur Wochen-Überblick, keine Nachrichten", "Weekly overview only, no messages")}</Badge>
              <Badge>{t("Freigabe liegt beim Kind – jederzeit widerrufbar", "Sharing is controlled by the child – revocable anytime")}</Badge>
            </div>
          </div>
        </div>
      </div>

      <div style={{ background: "#1a1c22", color: "#fff", padding: "30px 40px 22px", textAlign: "center" }}>
        <div style={{ maxWidth: 1180, margin: "0 auto", display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap", justifyContent: "center" }}>
          <span style={{ fontSize: 15, color: "#c5c9d2" }}>{t("Bereit? Es kostet zum Start nichts.", "Ready? It costs nothing to start.")}</span>
          <Link to="/login" style={{ fontSize: 14, fontWeight: 600, color: "#fff", background: "#6366f1", borderRadius: 11, padding: "10px 18px" }}>{t("Kostenlos loslegen →", "Start for free →")}</Link>
        </div>
        <div style={{ maxWidth: 1180, margin: "22px auto 0", paddingTop: 16, borderTop: "1px solid #2c2f38", display: "flex", gap: 18, flexWrap: "wrap", justifyContent: "center", fontSize: 12.5, color: "#8b909c" }}>
          <span>© {new Date().getFullYear()} Schrittweise</span>
          <Link to="/impressum" style={{ color: "#aab0bd" }}>{t("Impressum", "Legal notice")}</Link>
          <Link to="/datenschutz" style={{ color: "#aab0bd" }}>{t("Datenschutz", "Privacy")}</Link>
          <Link to="/agb" style={{ color: "#aab0bd" }}>{t("AGB", "Terms")}</Link>
          <span>{t("Verschlüsselte Übertragung · kein Klarname nötig", "Encrypted connection · no real name needed")}</span>
        </div>
      </div>
    </div>
  );
}
