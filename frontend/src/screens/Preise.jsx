import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../lib/api.js";
import { useShell } from "../components/AppShell.jsx";

function Feature({ children, color = "#1a7f3c" }) {
  return (
    <div style={{ fontSize: 13, display: "flex", gap: 9 }}>
      <span style={{ color, fontWeight: 700 }}>✓</span>
      {children}
    </div>
  );
}

export default function Preise() {
  const nav = useNavigate();
  const shell = useShell();
  const [params] = useSearchParams();
  const plan = shell.quota?.plan || "free";
  const [busyPkg, setBusyPkg] = useState(null); // Paket-Key waehrend des Checkouts
  const [note, setNote] = useState(null); // {type, text}

  // Rückkehr von der Stripe-Bezahlseite (?zahlung=ok|abbruch)
  useEffect(() => {
    const z = params.get("zahlung");
    if (z === "ok") {
      setNote({ type: "ok", text: "Zahlung erhalten – deine Tokens werden in wenigen Sekunden gutgeschrieben. 🎉" });
      // Webhook braucht evtl. 1–2 Sekunden; Kontingent verzögert nachladen
      const t1 = setTimeout(() => shell.reloadQuota?.(), 2500);
      const t2 = setTimeout(() => shell.reloadQuota?.(), 8000);
      return () => { clearTimeout(t1); clearTimeout(t2); };
    }
    if (z === "abbruch") {
      setNote({ type: "error", text: "Zahlung abgebrochen – es wurde nichts belastet." });
    }
  }, [params, shell]);

  async function buy(pkg) {
    setBusyPkg(pkg);
    setNote(null);
    try {
      const res = await api.post("/api/pay/checkout", { package: pkg });
      window.location.href = res.url; // weiter zur Stripe-Bezahlseite (Karte/TWINT)
    } catch (e) {
      setNote({ type: "error", text: e.message });
      setBusyPkg(null);
    }
  }

  // Sackgeld-Modell: drei Einmal-Pakete, kein Abo. 1 Token = 1 Rappen.
  const PAKETE = [
    { key: "schnupper", preis: "2.–", tokens: 200, hint: "≈ 100–200 Antworten · zum Reinschnuppern" },
    { key: "starter", preis: "9.–", tokens: 900, hint: "≈ 500–900 Antworten · der Klassiker" },
    { key: "power", preis: "19.–", tokens: 1900, hint: "≈ 1000–1900 Antworten", beliebt: true },
  ];

  return (
    <div style={{ height: "100%", overflowY: "auto", background: "#fbfbfd", padding: "36px 40px" }}>
      <div style={{ display: "flex", alignItems: "center", marginBottom: 24 }}>
        <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-.02em" }}>Preise &amp; Tokens</div>
        <span onClick={() => nav("/app/lernen")} style={{ marginLeft: "auto", fontSize: 12, fontWeight: 600, color: "#4f46e5", cursor: "pointer" }}>← zur App</span>
      </div>
      {note && (
        <div style={{ maxWidth: 920, margin: "0 auto 18px", fontSize: 13, borderRadius: 12, padding: "11px 16px", background: note.type === "error" ? "#fdecec" : "#e8f6ec", color: note.type === "error" ? "#c0392b" : "#1a7f3c", border: `1px solid ${note.type === "error" ? "#f5cccc" : "#cde7d6"}` }}>
          {note.text}
        </div>
      )}
      <div style={{ textAlign: "center", marginBottom: 28 }}>
        <div style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-.025em", marginBottom: 8 }}>Fair bleiben, ohne Bezahlschranke.</div>
        <div style={{ fontSize: 14, color: "#6b7280", maxWidth: "60ch", margin: "0 auto" }}>
          Üben kostet nichts zum Start. Wer mehr will, lädt Tokens oder nimmt das Schul-Abo.
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 18, maxWidth: 920, margin: "0 auto" }} className="preise-grid">
        {/* Gratis */}
        <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 18, padding: 24 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#6b7280", marginBottom: 12 }}>Gratis</div>
          <div style={{ fontSize: 32, fontWeight: 800, letterSpacing: "-.02em", marginBottom: 6 }}>0.–</div>
          <div style={{ fontSize: 12, color: "#9aa0ab", marginBottom: 20 }}>zum Ausprobieren</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 11, marginBottom: 22 }}>
            <Feature>50 Gratis-Tokens pro Monat</Feature>
            <Feature>Alle Themen</Feature>
            <Feature>Foto-Upload</Feature>
          </div>
          <div style={{ border: "1px solid #d2d4dd", borderRadius: 11, padding: 11, textAlign: "center", fontSize: 14, fontWeight: 600, color: plan === "free" ? "#1a1c22" : "#6b7280" }}>
            {plan === "free" ? "Aktueller Plan" : "Gratis"}
          </div>
        </div>

        {/* Token-Pakete (einmalig, kein Abo) */}
        <div style={{ background: "#1a1c22", borderRadius: 18, padding: 24, position: "relative", color: "#fff", transform: "translateY(-8px)", boxShadow: "0 20px 44px rgba(26,28,34,.28)" }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#c9ccf6", marginBottom: 4 }}>Token-Pakete</div>
          <div style={{ fontSize: 12, color: "#9aa0ab", marginBottom: 16 }}>einmalig kaufen · kein Abo · läuft nie ab</div>

          <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 18 }}>
            {PAKETE.map((p) => (
              <div key={p.key} style={{ background: p.beliebt ? "#26293346" : "transparent", border: `1px solid ${p.beliebt ? "#8b8ef7" : "#3a3d49"}`, borderRadius: 13, padding: "12px 14px", position: "relative" }}>
                {p.beliebt && (
                  <span style={{ position: "absolute", top: -9, right: 12, fontSize: 10, fontWeight: 700, color: "#1a1c22", background: "#fff", borderRadius: 999, padding: "2px 9px" }}>Beliebt</span>
                )}
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                      <span style={{ fontSize: 21, fontWeight: 800, letterSpacing: "-.02em" }}>{p.preis}</span>
                      <span style={{ fontSize: 12.5, color: "#c5c9d2" }}>{p.tokens} Tokens</span>
                    </div>
                    <div style={{ fontSize: 11, color: "#9aa0ab" }}>{p.hint}</div>
                  </div>
                  <button
                    onClick={() => buy(p.key)}
                    disabled={busyPkg !== null}
                    className="btn-primary"
                    style={{ borderRadius: 10, padding: "9px 15px", fontSize: 13, opacity: busyPkg && busyPkg !== p.key ? 0.5 : 1 }}
                  >
                    {busyPkg === p.key ? "Moment …" : "Kaufen"}
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 9, marginBottom: 14 }}>
            <Feature color="#8be0a4">1 Token = 1 Rappen KI-Hilfe</Feature>
            <Feature color="#8be0a4">Normale Antwort ≈ 1 Token · mit Foto ≈ 3–5</Feature>
            <Feature color="#8be0a4">Tokens laufen nie ab</Feature>
            <Feature color="#8be0a4">Karte oder TWINT</Feature>
          </div>
          <div style={{ fontSize: 11, color: "#9aa0ab", textAlign: "center" }}>
            Sichere Zahlung über Stripe · Minderjährige: bitte Eltern fragen
            <br />
            Mit dem Kauf akzeptierst du die <a href="/agb" target="_blank" rel="noreferrer" style={{ color: "#c9ccf6", textDecoration: "underline" }}>AGB</a>
          </div>
        </div>

        {/* Schule */}
        <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 18, padding: 24 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#6b7280", marginBottom: 12 }}>Schule / Klasse</div>
          <div style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-.02em", marginBottom: 6 }}>auf Anfrage</div>
          <div style={{ fontSize: 12, color: "#9aa0ab", marginBottom: 20 }}>pro Klasse / Jahr</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 11, marginBottom: 22 }}>
            <Feature>Unbegrenzt für alle</Feature>
            <Feature>Lehrpersonen-Dashboard</Feature>
            <Feature>Rechnung an die Schule</Feature>
          </div>
          <div style={{ border: "1px solid #d2d4dd", borderRadius: 11, padding: 11, textAlign: "center", fontSize: 14, fontWeight: 600 }}>Kontakt aufnehmen</div>
        </div>
      </div>
    </div>
  );
}
