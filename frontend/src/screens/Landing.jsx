import { Link, useNavigate } from "react-router-dom";

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
  return (
    <div style={{ minHeight: "100vh", background: "#fff", overflowX: "hidden" }}>
      <nav style={{ display: "flex", alignItems: "center", gap: 24, padding: "20px 40px", maxWidth: 1180, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ width: 26, height: 26, borderRadius: 8, background: "#6366f1" }} />
          <span style={{ fontWeight: 800, fontSize: 19, color: "#4f46e5", letterSpacing: "-.02em" }}>Schrittweise</span>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 14 }}>
          <Link to="/login" style={{ fontSize: 14, fontWeight: 600 }}>Anmelden</Link>
          <Link
            to="/login"
            style={{ fontSize: 14, fontWeight: 600, color: "#fff", background: "#6366f1", borderRadius: 11, padding: "10px 18px", boxShadow: "0 2px 10px rgba(99,102,241,.32)" }}
          >
            Kostenlos loslegen
          </Link>
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
            Mathe-Tutor · Schweizer Oberstufe
          </div>
          <h1 style={{ margin: "0 0 18px", fontSize: 54, lineHeight: 1.03, fontWeight: 900, letterSpacing: "-.035em", textWrap: "balance" }}>
            Mathe verstehen. Nicht abschreiben.
          </h1>
          <p style={{ margin: "0 0 28px", fontSize: 18, lineHeight: 1.55, color: "#4b5563", maxWidth: "46ch" }}>
            Dein Mathe-Tutor für die Oberstufe, der dir die Lösung nie einfach verrät – sondern dich Schritt für Schritt selber draufkommen lässt.
          </p>
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 24, flexWrap: "wrap" }}>
            <button onClick={() => nav("/login")} className="btn-primary" style={{ fontSize: 16, padding: "15px 26px", borderRadius: 13 }}>
              Kostenlos loslegen
            </button>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 18 }}>
            <Badge>Passt zum Lehrplan 21</Badge>
            <Badge>Verrät die Lösung nie direkt</Badge>
            <Badge>Kein Klarname nötig</Badge>
          </div>
        </div>

        {/* Chat-Vorschau mit Hinweis-Leiter */}
        <div style={{ position: "relative", zIndex: 1 }}>
          <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 22, boxShadow: "0 2px 6px rgba(40,40,90,.06),0 30px 60px rgba(40,40,90,.16)", overflow: "hidden" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "15px 18px", borderBottom: "1px solid #eef0f3" }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700 }}>Lineare Gleichungen</div>
                <div style={{ fontSize: 11.5, color: "#9aa0ab" }}>Aufgabe 3 von 8</div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 9, background: "#eef0fe", borderRadius: 999, padding: "6px 12px" }}>
                <span style={{ fontSize: 10.5, fontWeight: 700, color: "#4f46e5" }}>HINWEIS-LEITER</span>
                <span style={{ display: "flex", gap: 4 }}>
                  <Dot filled /><Dot filled /><Dot /><Dot />
                </span>
              </div>
            </div>
            <div style={{ background: "#f6f7fb", padding: 20, display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ alignSelf: "flex-start", background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, borderBottomLeftRadius: 5, boxShadow: "0 6px 16px rgba(40,40,90,.06)", padding: "11px 15px", fontSize: 13.5 }}>
                Löse nach x auf:
                <span style={{ fontFamily: "Georgia,serif", fontStyle: "italic", fontSize: 18, display: "inline-block", marginTop: 5 }}>3x + 5 = 20</span>
              </div>
              <div style={{ alignSelf: "flex-end", background: "#6366f1", color: "#fff", borderRadius: 16, borderBottomRightRadius: 5, padding: "10px 15px", fontSize: 13.5, maxWidth: "84%" }}>
                ich weiss nicht wie ich anfangen soll
              </div>
              <div style={{ alignSelf: "flex-start", background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, borderBottomLeftRadius: 5, boxShadow: "0 6px 16px rgba(40,40,90,.06)", padding: "11px 15px", fontSize: 13.5 }}>
                Kein Stress 🙂 Was müsstest du tun, damit die <b>+5</b> auf der linken Seite verschwindet?
              </div>
            </div>
          </div>
        </div>
      </div>

      <div style={{ background: "#1a1c22", color: "#fff", padding: "30px 40px 22px", textAlign: "center" }}>
        <div style={{ maxWidth: 1180, margin: "0 auto", display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap", justifyContent: "center" }}>
          <span style={{ fontSize: 15, color: "#c5c9d2" }}>Bereit? Es kostet zum Start nichts.</span>
          <Link to="/login" style={{ fontSize: 14, fontWeight: 600, color: "#fff", background: "#6366f1", borderRadius: 11, padding: "10px 18px" }}>zum Login →</Link>
        </div>
        <div style={{ maxWidth: 1180, margin: "22px auto 0", paddingTop: 16, borderTop: "1px solid #2c2f38", display: "flex", gap: 18, flexWrap: "wrap", justifyContent: "center", fontSize: 12.5, color: "#8b909c" }}>
          <span>© {new Date().getFullYear()} Schrittweise</span>
          <Link to="/impressum" style={{ color: "#aab0bd" }}>Impressum</Link>
          <Link to="/datenschutz" style={{ color: "#aab0bd" }}>Datenschutz</Link>
          <span>Verschlüsselte Übertragung · kein Klarname nötig</span>
        </div>
      </div>
    </div>
  );
}
