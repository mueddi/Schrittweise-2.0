import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { useLang } from "../lib/i18n.jsx";
import { useDialog } from "../lib/dialog.jsx";

// Schweizer Skala: 4.0 ist bestanden. Farben bewusst zurückhaltend – eine
// schlechte Note soll informieren, nicht bestrafen.
const BESTANDEN = 4.0;
const farbe = (n) => (n >= 5 ? "#1a7f3c" : n >= BESTANDEN ? "#4f46e5" : "#c0392b");

const TREND = {
  besser: ["↗ besser als vorher", "↗ better than before"],
  gleich: ["→ stabil", "→ steady"],
  schlechter: ["↘ zuletzt schwächer", "↘ weaker lately"],
};

/** Notenverlauf als handgezeichnete SVG-Linie.
 *
 * Kein Diagramm-Paket: das Projekt zeichnet seine Skizzen schon selbst
 * (MathFigure.jsx), und ein zusätzliches Paket würde das Bundle für eine
 * einzige Linie deutlich vergrössern.
 */
function Verlaufslinie({ noten }) {
  if (noten.length < 2) return null;
  const B = 420, H = 70, rand = 8;
  // Y-Achse fest auf 1–6: eine Note ist nur im Vergleich zur ganzen Skala
  // lesbar. Automatische Skalierung würde 4.0 → 4.2 wie einen Sprung zeigen.
  const y = (v) => rand + (6 - v) / 5 * (H - 2 * rand);
  const x = (i) => rand + (i / (noten.length - 1)) * (B - 2 * rand);
  const punkte = noten.map((n, i) => `${x(i).toFixed(1)},${y(n.value).toFixed(1)}`).join(" ");
  return (
    // Feste Groesse statt width="100%": bei voller Breite skaliert das Bild
    // seitenverhaeltnistreu auf die Hoehe und die Linie stand dann als kurzes
    // Stueck MITTIG im leeren Kasten. maxWidth schrumpft sie auf dem Handy mit.
    <svg viewBox={`0 0 ${B} ${H}`} width={B} height={H} role="img"
         aria-label="Notenverlauf" style={{ display: "block", marginTop: 6, maxWidth: "100%" }}>
      {/* Bestanden-Grenze als Orientierung */}
      <line x1={rand} y1={y(BESTANDEN)} x2={B - rand} y2={y(BESTANDEN)}
            stroke="#d2d4dd" strokeWidth="1" strokeDasharray="3 3" />
      <text x={B - rand} y={y(BESTANDEN) - 3} textAnchor="end"
            style={{ fontSize: 8, fill: "#9aa0ab" }}>4.0</text>
      <polyline points={punkte} fill="none" stroke="#6366f1" strokeWidth="2"
                strokeLinecap="round" strokeLinejoin="round" />
      {noten.map((n, i) => (
        <circle key={n.id} cx={x(i)} cy={y(n.value)} r="3.2" fill={farbe(n.value)} />
      ))}
    </svg>
  );
}

/** Noten eines Themas (oder alle, wenn topicId fehlt): Liste, Verlauf, Erfassen. */
export default function Noten({ topicId = null }) {
  const { t, lang } = useLang();
  const dialog = useDialog();
  const li = lang === "en" ? 1 : 0;
  const [verlauf, setVerlauf] = useState(null);
  const [offen, setOffen] = useState(false);
  const [wert, setWert] = useState("");
  const [datum, setDatum] = useState(() => new Date().toISOString().slice(0, 10));
  const [label, setLabel] = useState("");
  const [fehler, setFehler] = useState("");
  const [busy, setBusy] = useState(false);

  const laden = useCallback(async () => {
    const q = topicId ? `?topic_id=${topicId}` : "";
    try {
      setVerlauf(await api.get(`/api/grades/verlauf${q}`));
    } catch {
      setVerlauf(null);
    }
  }, [topicId]);
  useEffect(() => { laden(); }, [laden]);

  async function speichern() {
    const zahl = Number(String(wert).replace(",", "."));  // Schweizer Komma zulassen
    if (!Number.isFinite(zahl) || zahl < 1 || zahl > 6) {
      setFehler(t("Noten gehen von 1.0 bis 6.0.", "Grades run from 1.0 to 6.0."));
      return;
    }
    setBusy(true);
    setFehler("");
    try {
      await api.post("/api/grades", {
        value: Math.round(zahl * 10) / 10, taken_on: datum,
        topic_id: topicId ? Number(topicId) : null, label: label.trim(),
      });
      setWert(""); setLabel(""); setOffen(false);
      await laden();
    } catch (e) {
      // Der Server sagt, was los ist (z.B. Datum in der Zukunft)
      setFehler(e?.message || t("Das hat nicht geklappt.", "That didn't work."));
    } finally {
      setBusy(false);
    }
  }

  async function loeschen(id) {
    const ja = await dialog.bestaetigen({
      titel: t("Diese Note löschen?", "Delete this grade?"),
      text: t("Sie verschwindet aus dem Verlauf und aus dem Durchschnitt.",
              "It disappears from the history and from the average."),
      bestaetigen: t("Löschen", "Delete"),
      gefahr: true,
    });
    if (!ja) return;
    try {
      await api.del(`/api/grades/${id}`);
      await laden();
    } catch { /* Liste bleibt, wie sie ist */ }
  }

  const noten = verlauf?.noten || [];
  const kasten = { background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, padding: 18 };

  return (
    <div style={{ ...kasten, marginBottom: 18 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: noten.length ? 12 : 0 }}>
        <div style={{ fontSize: 15, fontWeight: 700 }}>{t("Noten", "Grades")}</div>
        <button onClick={() => setOffen((v) => !v)}
                style={{ border: "1px solid #dcdff5", background: "#f8f8ff", color: "#4f46e5", borderRadius: 999, padding: "6px 13px", fontSize: 12.5, fontWeight: 600, cursor: "pointer" }}>
          {offen ? t("Abbrechen", "Cancel") : t("+ Note eintragen", "+ Add grade")}
        </button>
      </div>

      {offen && (
        <div className="popin" style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 14, background: "#fbfbfd", border: "1px solid #e7e8ee", borderRadius: 12, padding: 12 }}>
          <input autoFocus value={wert} onChange={(e) => setWert(e.target.value)}
                 onKeyDown={(e) => e.key === "Enter" && speichern()}
                 inputMode="decimal" placeholder={t("Note, z.B. 4.5", "Grade, e.g. 4.5")}
                 style={{ width: 120, border: "1px solid #d2d4dd", borderRadius: 10, padding: "9px 12px", fontSize: 14, outline: "none" }} />
          <input type="date" value={datum} max={new Date().toISOString().slice(0, 10)}
                 onChange={(e) => setDatum(e.target.value)}
                 style={{ border: "1px solid #d2d4dd", borderRadius: 10, padding: "9px 12px", fontSize: 14, outline: "none" }} />
          <input value={label} onChange={(e) => setLabel(e.target.value)}
                 onKeyDown={(e) => e.key === "Enter" && speichern()}
                 placeholder={t("Titel (optional)", "Title (optional)")}
                 style={{ flex: "1 1 140px", border: "1px solid #d2d4dd", borderRadius: 10, padding: "9px 12px", fontSize: 14, outline: "none" }} />
          <button onClick={speichern} disabled={busy} className="btn-primary"
                  style={{ padding: "9px 16px", borderRadius: 10, fontSize: 13, border: "none", opacity: busy ? 0.6 : 1 }}>
            {t("Speichern", "Save")}
          </button>
          {fehler && <div style={{ flexBasis: "100%", fontSize: 12.5, color: "#c0392b" }}>{fehler}</div>}
        </div>
      )}

      {noten.length === 0 ? (
        <div style={{ fontSize: 13, color: "#6b7280", marginTop: 10 }}>
          {t("Noch keine Note erfasst. Trag deine Prüfungsnoten ein – dann siehst du den Verlauf.",
             "No grades yet. Add your test results to see the trend.")}
        </div>
      ) : (
        <>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
            <span style={{ fontSize: 26, fontWeight: 800, color: farbe(verlauf.schnitt) }}>
              {verlauf.schnitt?.toFixed(1)}
            </span>
            <span style={{ fontSize: 12.5, color: "#6b7280" }}>
              {t("Schnitt aus", "average of")} {noten.length} {noten.length === 1 ? t("Note", "grade") : t("Noten", "grades")}
            </span>
            {noten.length >= 2 && (
              <span style={{ fontSize: 12, fontWeight: 700, color: verlauf.trend === "besser" ? "#1a7f3c" : verlauf.trend === "schlechter" ? "#c0392b" : "#6b7280" }}>
                {TREND[verlauf.trend][li]}
              </span>
            )}
          </div>
          <Verlaufslinie noten={noten} />
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 12 }}>
            {[...noten].reverse().map((n) => (
              <div key={n.id} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13 }}>
                <span style={{ width: 38, fontWeight: 800, color: farbe(n.value) }}>{n.value.toFixed(1)}</span>
                <span style={{ color: "#9aa0ab", width: 86 }}>{n.taken_on}</span>
                <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {n.label || (n.source === "probe" ? t("Probeprüfung", "Practice test") : "")}
                </span>
                {n.source === "probe" && (
                  <span style={{ fontSize: 10.5, fontWeight: 700, borderRadius: 999, padding: "2px 8px", background: "#eef0fe", color: "#4f46e5" }}>
                    {t("geschätzt", "estimated")}
                  </span>
                )}
                <button onClick={() => loeschen(n.id)} aria-label={t("Note löschen", "Delete grade")}
                        style={{ border: "none", background: "none", color: "#b6bcc6", cursor: "pointer", fontSize: 15, lineHeight: 1 }}>×</button>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
