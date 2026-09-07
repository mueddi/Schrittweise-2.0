import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { Tile } from "./Eltern.jsx";
import { useLang } from "../lib/i18n.jsx";

// Admin-Seite «Störungen»: nicht die rohen Fehlertexte, sondern die Antwort
// auf die Frage, die der Betreiber wirklich hat – muss ich etwas tun?
// Einordnung und Texte kommen vom Server (services/stoerungen.py).
const STUFE = {
  handeln: { farbe: "#d9573a", hell: "#fdf0ee", rand: "#f2c9c0", icon: "🔴" },
  pruefen: { farbe: "#c98a12", hell: "#fdf8ec", rand: "#f0dcae", icon: "🟠" },
  keine: { farbe: "#1a7f3c", hell: "#eef8f0", rand: "#c6e6cf", icon: "🟢" },
};

export default function Stoerungen() {
  const { t } = useLang();
  const [tage, setTage] = useState(30);
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [offen, setOffen] = useState({});

  const label = {
    handeln: t("Handlungsbedarf", "Action needed"),
    pruefen: t("Prüfen", "Check"),
    keine: t("Kein Handlungsbedarf", "No action needed"),
  };

  useEffect(() => {
    let alive = true;
    api
      .get(`/api/admin/stoerungen?tage=${tage}`)
      .then((d) => alive && (setData(d), setErr("")))
      .catch((e) => alive && setErr(e.message || t("Konnte die Störungen nicht laden.", "Could not load incidents.")));
    return () => {
      alive = false;
    };
  }, [tage]); // eslint-disable-line react-hooks/exhaustive-deps

  const zeit = (iso) => (iso ? new Date(iso).toLocaleString("de-CH", { dateStyle: "short", timeStyle: "short" }) : "–");

  return (
    <div style={{ flex: 1, overflowY: "auto", background: "#fbfbfd" }}>
      <div style={{ maxWidth: 860, margin: "0 auto", padding: "28px 20px 60px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 6 }}>
          <h1 style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-.02em", margin: 0 }}>{t("⚠️ Störungen", "⚠️ Incidents")}</h1>
          <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
            {[7, 30, 90].map((n) => (
              <button
                key={n}
                onClick={() => setTage(n)}
                style={{
                  padding: "7px 13px",
                  borderRadius: 999,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: "pointer",
                  border: "1px solid " + (tage === n ? "#4f46e5" : "#e7e8ee"),
                  background: tage === n ? "#eef0fe" : "#fff",
                  color: tage === n ? "#4f46e5" : "#6b7280",
                }}
              >
                {n} {t("Tage", "days")}
              </button>
            ))}
          </div>
        </div>
        <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 20 }}>
          {t("Was passiert ist, was es für die Nutzer heisst – und ob du etwas tun musst.", "What happened, what it means for users – and whether you need to act.")}
        </div>

        {err && (
          <div style={{ background: "#fdf0ee", border: "1px solid #f2c9c0", color: "#b3492f", borderRadius: 12, padding: "12px 16px", fontSize: 13, marginBottom: 16 }}>
            {err}
          </div>
        )}
        {!data && !err && <div style={{ fontSize: 13, color: "#9aa0ab" }}>{t("lädt …", "loading …")}</div>}

        {data && (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12, marginBottom: 20 }}>
              {["handeln", "pruefen", "keine"].map((s) => (
                <Tile key={s} label={`${STUFE[s].icon} ${label[s]}`} value={data.stand[s]} sub={t("Arten von Störungen", "kinds of incidents")} color={data.stand[s] > 0 || s === "keine" ? STUFE[s].farbe : "#9aa0ab"} />
              ))}
              <Tile label={t("Meldungen gesamt", "Messages total")} value={data.meldungen_gesamt} sub={`${data.zeitraum_tage} ${t("Tage", "days")}`} />
            </div>

            {data.gruppen.length === 0 && (
              <div style={{ background: "#eef8f0", border: "1px solid #c6e6cf", borderRadius: 16, padding: 20, fontSize: 13, color: "#1a7f3c", fontWeight: 600 }}>
                {t("Keine Störungen im gewählten Zeitraum.", "No incidents in the selected period.")}
              </div>
            )}

            {data.gruppen.map((g) => {
              const s = STUFE[g.stufe] || STUFE.pruefen;
              const auf = !!offen[g.id];
              return (
                <div key={g.id} style={{ background: "#fff", border: `1px solid ${s.rand}`, borderLeft: `5px solid ${s.farbe}`, borderRadius: 16, padding: 18, marginBottom: 14 }}>
                  <div style={{ display: "flex", alignItems: "flex-start", gap: 10, flexWrap: "wrap" }}>
                    <div style={{ flex: 1, minWidth: 220 }}>
                      <div style={{ fontSize: 15, fontWeight: 800, marginBottom: 2 }}>{g.titel}</div>
                      <div style={{ fontSize: 12, color: "#9aa0ab" }}>
                        {g.label} · {g.anzahl}× {t("in", "in")} {data.zeitraum_tage} {t("Tagen", "days")}
                        {g.anzahl_24h > 0 && ` · ${g.anzahl_24h}× ${t("in den letzten 24 h", "in the last 24 h")}`}
                        {" · "}{t("zuletzt", "last")} {zeit(g.letzter)}
                      </div>
                    </div>
                    <span style={{ fontSize: 12, fontWeight: 700, color: s.farbe, background: s.hell, border: `1px solid ${s.rand}`, borderRadius: 999, padding: "5px 11px", whiteSpace: "nowrap" }}>
                      {s.icon} {label[g.stufe]}
                      {g.gehaeuft && ` · ${t("gehäuft", "recurring")}`}
                    </span>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14, marginTop: 14 }}>
                    <div>
                      <div style={kopf}>{t("Was passiert ist", "What happened")}</div>
                      <div style={text}>{g.bedeutung}</div>
                    </div>
                    <div>
                      <div style={kopf}>{t("Was zu tun ist", "What to do")}</div>
                      <div style={{ ...text, fontWeight: g.stufe === "handeln" ? 600 : 400 }}>{g.massnahme}</div>
                    </div>
                  </div>

                  <div style={{ marginTop: 12 }}>
                    <div style={kopf}>{t("Letzte Meldung", "Latest message")}</div>
                    <pre style={code}>{g.meldungen[0]?.detail || "–"}</pre>
                    {g.meldungen.length > 1 && (
                      <button onClick={() => setOffen({ ...offen, [g.id]: !auf })} style={{ background: "none", border: "none", color: "#4f46e5", fontSize: 12, fontWeight: 600, cursor: "pointer", padding: 0, marginTop: 6 }}>
                        {auf ? t("weniger", "less") : t(`alle ${g.meldungen.length} letzten Meldungen zeigen`, `show all ${g.meldungen.length} latest messages`)}
                      </button>
                    )}
                    {auf && g.meldungen.slice(1).map((m, i) => (
                      <div key={i} style={{ marginTop: 8 }}>
                        <div style={{ fontSize: 11, color: "#9aa0ab" }}>{zeit(m.zeit)}</div>
                        <pre style={code}>{m.detail}</pre>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}

            <div style={{ fontSize: 12, color: "#9aa0ab", marginTop: 16, lineHeight: 1.6 }}>
              {data.drossel_hinweis}{" "}
              {t("Einzelheiten zu jedem Fehler stehen in den Vercel-Laufzeitprotokollen (Projekt → Logs).", "Details of every error are in the Vercel runtime logs (project → Logs).")}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

const kopf = { fontSize: 11, fontWeight: 700, letterSpacing: ".05em", color: "#9aa0ab", marginBottom: 4, textTransform: "uppercase" };
const text = { fontSize: 13, lineHeight: 1.55, color: "#1a1c22" };
const code = { fontSize: 12, background: "#f6f7fa", border: "1px solid #eef0f3", borderRadius: 8, padding: "8px 10px", whiteSpace: "pre-wrap", wordBreak: "break-word", margin: 0, color: "#3b3f4a", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace" };
