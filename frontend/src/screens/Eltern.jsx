import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api.js";

// Zwei Dinge, sauber getrennt:
// - ChildDashboard: das echte Eltern-Dashboard (genutzt von ParentDashboard.jsx)
// - Eltern (default): die SCHUELER-Seite «Eltern verbinden» – nur Code +
//   Erklaerung, KEIN Dashboard-Klon in der Kinder-App.
const TAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];

// Backend-Labels -> elternverstaendliche Chips
const LABEL_TEXT = { "Noch üben": "Braucht Hilfe", "Wird besser": "Wird besser", Sitzt: "Sitzt" };
const LABEL_STYLE = {
  "Braucht Hilfe": { bg: "#fdecec", fg: "#c0392b" },
  "Wird besser": { bg: "#eef0fe", fg: "#4f46e5" },
  Sitzt: { bg: "#e8f6ec", fg: "#1a7f3c" },
};

export function Tile({ label, value, unit, sub, color = "#1a1c22" }) {
  return (
    <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, padding: 18 }}>
      <div style={{ fontSize: 12, color: "#9aa0ab", marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 800, letterSpacing: "-.02em", color }}>
        {value}
        {unit && <span style={{ fontSize: 16 }}>{unit}</span>}
      </div>
      <div style={{ fontSize: 12, color: "#6b7280", marginTop: 4 }}>{sub}</div>
    </div>
  );
}

// Klartext-Zusammenfassung aus den echten Wochendaten – das Wichtigste in
// einem Satz, ohne Prozent-Jargon.
function summarySentence(d) {
  const name = d.student_display_name;
  if (!d.solved_count && !d.active_days) {
    return `${name} hat diese Woche noch nicht geübt.`;
  }
  const autonomous = Math.round((d.autonomy_rate / 100) * d.solved_count);
  let s = `${name} hat diese Woche an ${d.active_days} ${d.active_days === 1 ? "Tag" : "Tagen"} geübt`;
  s += d.solved_count
    ? ` und ${d.solved_count} ${d.solved_count === 1 ? "Aufgabe" : "Aufgaben"} gelöst – ${autonomous} davon fast ohne Hilfe.`
    : ", aber noch keine Aufgabe fertig gelöst.";
  const worst = (d.top_struggles || [])[0];
  if (worst) s += ` Beim Thema «${worst.topic}» war mehrmals viel Hilfe nötig.`;
  return s;
}

function trendText(delta) {
  if (delta > 15) return { value: "mehr", sub: "geübt als letzte Woche", color: "#1a7f3c" };
  if (delta < -15) return { value: "weniger", sub: "geübt als letzte Woche", color: "#c0392b" };
  return { value: "etwa gleich", sub: "viel wie letzte Woche", color: "#4f46e5" };
}

export function ChildDashboard({ data }) {
  const struggles = data.top_struggles || [];
  const daily = data.daily_activity || [0, 0, 0, 0, 0, 0, 0];
  const maxV = Math.max(...daily, 1);
  const trend = trendText(data.dranbleiben_delta || 0);
  return (
    <>
      {/* Das Wichtigste zuerst: ein Satz in Klartext, aus echten Daten */}
      <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, padding: "16px 20px", fontSize: 15, lineHeight: 1.6, marginBottom: 20 }}>
        {summarySentence(data)}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16, marginBottom: 20 }} className="eltern-tiles">
        <Tile label="Gelöste Aufgaben" value={data.solved_count} sub="diese Woche" />
        <Tile label="Löst selbständig" value={data.autonomy_rate} unit="%" sub="der gelösten Aufgaben fast ohne Hilfe" color="#1a7f3c" />
        <Tile label="Übungstage" value={data.active_days} unit=" von 7" sub="diese Woche" />
        <Tile label="Trend" value={trend.value} sub={trend.sub} color={trend.color} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 16 }} className="eltern-charts">
        <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, padding: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>Themen mit viel Hilfebedarf</div>
          <div style={{ fontSize: 12, color: "#9aa0ab", marginBottom: 14 }}>hier lohnt sich gemeinsames Üben</div>
          {struggles.length === 0 && <div style={{ fontSize: 13, color: "#9aa0ab" }}>Kein Thema auffällig – läuft rund.</div>}
          {struggles.map((t) => {
            const label = LABEL_TEXT[t.label] || t.label;
            const st = LABEL_STYLE[label] || { bg: "#f1f2f6", fg: "#6b7280" };
            return (
              <div key={t.topic} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "9px 0", borderTop: "1px solid #f4f5f8" }}>
                <span style={{ fontSize: 13.5, fontWeight: 600 }}>{t.topic}</span>
                <span style={{ fontSize: 11, fontWeight: 700, borderRadius: 999, padding: "4px 11px", background: st.bg, color: st.fg }}>{label}</span>
              </div>
            );
          })}
        </div>
        <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, padding: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 16 }}>An welchen Tagen geübt wurde</div>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 90 }}>
            {daily.map((v, i) => {
              const h = Math.max(Math.round((v / maxV) * 74), v > 0 ? 10 : 2);
              return (
                <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                  <div title={`${v} ${v === 1 ? "Aufgabe" : "Aufgaben"}`} style={{ width: "100%", height: h, background: v > 0 ? (v >= maxV ? "#6366f1" : "#e7e8fb") : "#eef0f3", borderRadius: 6 }} />
                  <span style={{ fontSize: 10, color: "#9aa0ab" }}>{TAGE[i]}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
      <div style={{ marginTop: 16, fontSize: 12.5, color: "#9aa0ab" }}>
        🔒 Sie sehen den groben Fortschritt – nie einzelne Nachrichten Ihres Kindes.
      </div>
    </>
  );
}

// SCHUELER-Seite: nur Eltern verbinden – kein Dashboard in der Kinder-App.
export default function Eltern() {
  const [invite, setInvite] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.get("/api/parents/invite").then(setInvite).catch(() => setInvite(null));
  }, []);

  return (
    <div style={{ height: "100%", overflowY: "auto", background: "#fbfbfd", padding: "36px 40px" }}>
      <div style={{ maxWidth: 620, margin: "0 auto" }}>
        <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-.02em", marginBottom: 6 }}>Eltern verbinden</div>
        <div style={{ fontSize: 14, color: "#6b7280", marginBottom: 24, lineHeight: 1.55 }}>
          Deine Eltern erstellen ein eigenes Eltern-Konto und geben dort diesen Code ein.
        </div>

        {invite ? (
          <div style={{ background: "#eef0fe", border: "1px solid #dfe1fb", borderRadius: 18, padding: "22px 24px", textAlign: "center", marginBottom: 20 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#4f46e5", marginBottom: 10 }}>DEIN EINLADUNGSCODE</div>
            <div style={{ fontFamily: "ui-monospace, monospace", fontSize: 30, fontWeight: 800, letterSpacing: ".22em", color: "#1a1c22", background: "#fff", borderRadius: 12, padding: "12px 18px", border: "1px solid #dfe1fb", display: "inline-block", marginBottom: 14 }}>
              {invite.invite_code}
            </div>
            <div>
              <button
                onClick={() => { navigator.clipboard?.writeText(invite.invite_code); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
                className="btn-primary"
                style={{ padding: "10px 20px", borderRadius: 10, fontSize: 13, border: "none" }}
              >
                {copied ? "kopiert ✓" : "Code kopieren"}
              </button>
            </div>
          </div>
        ) : (
          <div style={{ color: "#9aa0ab", fontSize: 14, marginBottom: 20 }}>lädt …</div>
        )}

        <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, padding: "18px 22px", marginBottom: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>Das sehen deine Eltern</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 9, fontSize: 13.5, color: "#3a3d46" }}>
            <div><span style={{ color: "#1a7f3c", fontWeight: 700 }}>✓</span> Wie viele Aufgaben du diese Woche gelöst hast</div>
            <div><span style={{ color: "#1a7f3c", fontWeight: 700 }}>✓</span> Wie selbständig du arbeitest</div>
            <div><span style={{ color: "#1a7f3c", fontWeight: 700 }}>✓</span> An welchen Tagen du geübt hast</div>
            <div><span style={{ color: "#c0392b", fontWeight: 700 }}>✗</span> <b>Nie</b> deine Nachrichten mit dem Tutor – die bleiben privat</div>
          </div>
        </div>

        <div style={{ fontSize: 12.5, color: "#9aa0ab", lineHeight: 1.55 }}>
          Du kannst die Freigabe jederzeit ausschalten:{" "}
          <Link to="/app/einstellungen" style={{ color: "#4f46e5", fontWeight: 600 }}>Einstellungen → Privatsphäre</Link>
        </div>
      </div>
    </div>
  );
}
