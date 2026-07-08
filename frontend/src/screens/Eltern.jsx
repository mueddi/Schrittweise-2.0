import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";

// Schüler-Vorschau der Eltern-Ansicht: exakt das, was Eltern spaeter sehen,
// plus der Einladungscode zum Teilen. Echte Aggregate, nie Transkripte.
const TAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const LABEL_COLOR = { Sitzt: "#1a7f3c", "Wird besser": "#4f46e5", "Noch üben": "#c0392b" };
const LABEL_BAR = { Sitzt: "#1a7f3c", "Wird besser": "#6366f1", "Noch üben": "#d9573a" };
const LABEL_PCT = { Sitzt: 100, "Wird besser": 62, "Noch üben": 25 };

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

export function ChildDashboard({ data }) {
  const struggles = data.top_struggles || [];
  const daily = data.daily_activity || [0, 0, 0, 0, 0, 0, 0];
  const maxV = Math.max(...daily, 1);
  return (
    <>
      <div style={{ fontSize: 14, color: "#6b7280", marginBottom: 20, maxWidth: "70ch" }}>
        Du siehst den groben Fortschritt – nicht jede Nachricht. Gemessen wird, wie selbständig gelöst wird.
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16, marginBottom: 20 }} className="eltern-tiles">
        <Tile label="Selbständigkeit" value={data.autonomy_rate} unit="%" sub="löst ohne grosse Hilfe" color="#1a7f3c" />
        <Tile label="Aufgaben gelöst" value={data.solved_count} sub="diese Woche" />
        <Tile label="Aktive Tage" value={data.active_days} unit=" / 7" sub="ohne Druck-Streaks" />
        <Tile label="Dranbleiben" value={(data.dranbleiben_delta >= 0 ? "+" : "") + data.dranbleiben_delta} unit="%" sub="vs. letzte Woche" color="#4f46e5" />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 16 }} className="eltern-charts">
        <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, padding: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 16 }}>Stolpersteine &amp; Themen</div>
          {struggles.length === 0 && <div style={{ fontSize: 13, color: "#9aa0ab" }}>Noch keine auffälligen Themen – läuft rund.</div>}
          {struggles.map((t) => (
            <div key={t.topic} style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 13 }}>
              <span style={{ flex: "0 0 150px", fontSize: 13, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{t.topic}</span>
              <div style={{ flex: 1, height: 8, borderRadius: 999, background: "#eef0f3", overflow: "hidden" }}>
                <div style={{ width: `${LABEL_PCT[t.label] ?? 40}%`, height: "100%", background: LABEL_BAR[t.label] || "#6366f1" }} />
              </div>
              <span style={{ fontSize: 11, fontWeight: 700, color: LABEL_COLOR[t.label] || "#4f46e5", width: 78, textAlign: "right" }}>{t.label}</span>
            </div>
          ))}
        </div>
        <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, padding: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 16 }}>Aktivität</div>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 90 }}>
            {daily.map((v, i) => {
              const h = Math.max(Math.round((v / maxV) * 74), v > 0 ? 10 : 2);
              return (
                <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                  <div style={{ width: "100%", height: h, background: v > 0 ? (v >= maxV ? "#6366f1" : "#e7e8fb") : "#eef0f3", borderRadius: 6 }} />
                  <span style={{ fontSize: 10, color: "#9aa0ab" }}>{TAGE[i]}</span>
                </div>
              );
            })}
          </div>
          <div style={{ fontSize: 12, color: "#6b7280", marginTop: 14, lineHeight: 1.5 }}>Ruhige Nutzung – keine Push-Benachrichtigungen.</div>
        </div>
      </div>
    </>
  );
}

export default function Eltern() {
  const nav = useNavigate();
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [invite, setInvite] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.get("/api/parents/preview").then(setData).catch(() => setData(null));
    api.get("/api/parents/invite").then(setInvite).catch(() => setInvite(null));
  }, []);

  return (
    <div style={{ height: "100%", overflowY: "auto", background: "#fbfbfd" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 28px", borderBottom: "1px solid #eef0f3", background: "#fff" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <span style={{ width: 22, height: 22, borderRadius: 7, background: "#6366f1" }} />
          <span style={{ fontWeight: 800, fontSize: 16, color: "#4f46e5", letterSpacing: "-.02em" }}>Schrittweise</span>
          <span style={{ fontSize: 12, fontWeight: 600, color: "#6b7280", background: "#f1f2f6", borderRadius: 999, padding: "4px 12px", marginLeft: 8 }}>Elternansicht (Vorschau)</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <span style={{ fontSize: 13, color: "#6b7280" }}>Diese Woche ▾</span>
          <span onClick={() => nav("/app/lernen")} style={{ fontSize: 12, fontWeight: 600, color: "#4f46e5", cursor: "pointer" }}>← zur App</span>
        </div>
      </div>

      <div style={{ padding: "24px 28px" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 4 }}>
          <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-.02em" }}>{user?.display_name} · {user?.grade_level || "Oberstufe"}</div>
          <div style={{ fontSize: 13, color: "#9aa0ab" }}>so sehen es deine Eltern</div>
        </div>

        {/* Einladungscode */}
        {invite && (
          <div style={{ display: "flex", alignItems: "center", gap: 16, background: "#eef0fe", border: "1px solid #dfe1fb", borderRadius: 16, padding: "14px 18px", margin: "12px 0 20px" }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#4f46e5", marginBottom: 2 }}>Eltern einladen</div>
              <div style={{ fontSize: 12, color: "#6b7280" }}>Gib deinen Eltern diesen Code. Sie sehen nur diesen groben Fortschritt – keine Nachrichten.</div>
            </div>
            <div style={{ fontFamily: "ui-monospace, monospace", fontSize: 20, fontWeight: 800, letterSpacing: ".18em", color: "#1a1c22", background: "#fff", borderRadius: 10, padding: "8px 16px", border: "1px solid #dfe1fb" }}>{invite.invite_code}</div>
            <button onClick={() => { navigator.clipboard?.writeText(invite.invite_code); setCopied(true); setTimeout(() => setCopied(false), 1500); }} className="btn-primary" style={{ padding: "10px 16px", borderRadius: 10, fontSize: 13, border: "none" }}>
              {copied ? "kopiert ✓" : "Code kopieren"}
            </button>
          </div>
        )}

        {data ? <ChildDashboard data={data} /> : <div style={{ color: "#9aa0ab", fontSize: 14 }}>lädt …</div>}

        <div style={{ marginTop: 20, background: "#f6f7fb", border: "1px solid #eef0f3", borderRadius: 14, padding: 16, fontSize: 13, color: "#6b7280", lineHeight: 1.55 }}>
          🔒 «Du siehst den groben Fortschritt – nicht jede Nachricht.» Aus der Eltern-Ansicht gibt es technisch keinen Zugriff auf deine Chats.
        </div>
      </div>
    </div>
  );
}
