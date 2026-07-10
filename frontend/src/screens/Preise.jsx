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
  const [busy, setBusy] = useState(false);
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

  async function buy() {
    setBusy(true);
    setNote(null);
    try {
      const res = await api.post("/api/pay/checkout", {});
      window.location.href = res.url; // weiter zur Stripe-Bezahlseite (Karte/TWINT)
    } catch (e) {
      setNote({ type: "error", text: e.message });
      setBusy(false);
    }
  }

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
            <Feature>20 Aufgaben pro Monat</Feature>
            <Feature>Alle Themen</Feature>
            <Feature>Foto-Upload</Feature>
          </div>
          <div style={{ border: "1px solid #d2d4dd", borderRadius: 11, padding: 11, textAlign: "center", fontSize: 14, fontWeight: 600, color: plan === "free" ? "#1a1c22" : "#6b7280" }}>
            {plan === "free" ? "Aktueller Plan" : "Gratis"}
          </div>
        </div>

        {/* Token-Paket */}
        <div style={{ background: "#1a1c22", borderRadius: 18, padding: 24, position: "relative", color: "#fff", transform: "translateY(-8px)", boxShadow: "0 20px 44px rgba(26,28,34,.28)" }}>
          <span style={{ position: "absolute", top: 16, right: 16, fontSize: 11, fontWeight: 700, color: "#1a1c22", background: "#fff", borderRadius: 999, padding: "4px 10px" }}>Beliebt</span>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#c9ccf6", marginBottom: 12 }}>Token-Paket</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginBottom: 6 }}>
            <span style={{ fontSize: 32, fontWeight: 800, letterSpacing: "-.02em" }}>19.–</span>
            <span style={{ fontSize: 14, color: "#9aa0ab" }}>/ einmalig</span>
          </div>
          <div style={{ fontSize: 12, color: "#9aa0ab", marginBottom: 20 }}>300 Aufgaben · läuft nicht ab</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 11, marginBottom: 22 }}>
            <Feature color="#8be0a4">300 Aufgaben</Feature>
            <Feature color="#8be0a4">Kein Ablaufdatum</Feature>
            <Feature color="#8be0a4">Priorität bei Antwortzeit</Feature>
          </div>
          <button
            onClick={buy}
            disabled={busy}
            className="btn-primary"
            style={{ width: "100%", borderRadius: 11, padding: 12, fontSize: 14, opacity: busy ? 0.6 : 1 }}
          >
            {busy ? "einen Moment …" : "Tokens kaufen"}
          </button>
          <div style={{ fontSize: 11, color: "#9aa0ab", textAlign: "center", marginTop: 10 }}>
            Sichere Zahlung über Stripe · Karte oder TWINT
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
