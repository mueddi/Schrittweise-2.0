import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";
import { useLang } from "../lib/i18n.jsx";

// Zwei Dinge, sauber getrennt:
// - ChildDashboard: das echte Eltern-Dashboard (genutzt von ParentDashboard.jsx)
// - Eltern (default): die SCHUELER-Seite «Eltern verbinden» – nur Code +
//   Erklaerung, KEIN Dashboard-Klon in der Kinder-App.

// Backend-Labels -> elternverstaendliche Chips (Keys sind Backend-Werte, nicht anfassen)
function labelChip(raw, t) {
  const map = {
    "Noch üben": { text: t("Braucht Hilfe", "Needs help"), bg: "#fdecec", fg: "#c0392b" },
    "Braucht Hilfe": { text: t("Braucht Hilfe", "Needs help"), bg: "#fdecec", fg: "#c0392b" },
    "Wird besser": { text: t("Wird besser", "Improving"), bg: "#eef0fe", fg: "#4f46e5" },
    Sitzt: { text: t("Sitzt", "Solid"), bg: "#e8f6ec", fg: "#1a7f3c" },
  };
  return map[raw] || { text: raw, bg: "#f1f2f6", fg: "#6b7280" };
}

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
function summarySentence(d, t) {
  const name = d.student_display_name;
  if (!d.solved_count && !d.active_days) {
    return t(`${name} hat diese Woche noch nicht geübt.`, `${name} hasn't practiced yet this week.`);
  }
  const autonomous = Math.round((d.autonomy_rate / 100) * d.solved_count);
  let s = t(
    `${name} hat diese Woche an ${d.active_days} ${d.active_days === 1 ? "Tag" : "Tagen"} geübt`,
    `${name} practiced on ${d.active_days} ${d.active_days === 1 ? "day" : "days"} this week`
  );
  s += d.solved_count
    ? t(
        ` und ${d.solved_count} ${d.solved_count === 1 ? "Aufgabe" : "Aufgaben"} gelöst – ${autonomous} davon fast ohne Hilfe.`,
        ` and solved ${d.solved_count} ${d.solved_count === 1 ? "task" : "tasks"} – ${autonomous} of them almost without help.`
      )
    : t(", aber noch keine Aufgabe fertig gelöst.", ", but hasn't fully solved a task yet.");
  const worst = (d.top_struggles || [])[0];
  if (worst) {
    s += t(
      ` Beim Thema «${worst.topic}» war mehrmals viel Hilfe nötig.`,
      ` The topic "${worst.topic}" needed a lot of help several times.`
    );
  }
  return s;
}

// Regelbasierte, konkrete Hilfe-Tipps aus den Wochen-Zahlen (max. 2).
function helpTips(d, t) {
  const tips = [];
  const worst = (d.top_struggles || [])[0];
  if (worst) {
    const topicLabel = worst.topic === "Ohne Thema"
      ? t("den Aufgaben ohne Thema", "the tasks without a topic")
      : `«${worst.topic}»`;
    tips.push(t(
      `Setzen Sie bei ${topicLabel} an: Lassen Sie sich 2–3 gelöste Aufgaben Schritt für Schritt erklären – wer erklärt, festigt das Verständnis am stärksten.`,
      `Start with ${topicLabel}: have your child explain 2–3 solved tasks step by step – explaining is the strongest way to consolidate understanding.`
    ));
  }
  if ((d.active_days ?? 0) <= 1) {
    tips.push(t(
      "Regelmässigkeit schlägt Länge: 3× pro Woche 15 Minuten bringen mehr als eine lange Sitzung. Ein fester Übungsmoment (z.B. nach dem Znacht) hilft.",
      "Consistency beats length: 15 minutes 3× a week beats one long session. A fixed practice moment (e.g. after dinner) helps."
    ));
  }
  if ((d.autonomy_rate ?? 0) < 40 && (d.solved_count ?? 0) >= 3) {
    tips.push(t(
      "Viel Hilfe genutzt: Ermutigen Sie Ihr Kind, vor jedem Tipp zuerst einen eigenen Versuch zu schreiben – der Tutor gibt die Lösung nie direkt vor.",
      "A lot of help was used: encourage your child to write an own attempt before each hint – the tutor never gives the answer away."
    ));
  }
  if (tips.length === 0) {
    tips.push(t(
      "Läuft rund! Benennen Sie den Fortschritt konkret («Du hast das diese Woche selbständig gelöst») – das wirkt stärker als Lob fürs Resultat.",
      "Going well! Name the progress specifically (“you solved that on your own this week”) – that works better than praising results."
    ));
  }
  return tips.slice(0, 2);
}

function trendText(delta, t) {
  if (delta > 15) return { value: t("mehr", "more"), sub: t("geübt als letzte Woche", "practice than last week"), color: "#1a7f3c" };
  if (delta < -15) return { value: t("weniger", "less"), sub: t("geübt als letzte Woche", "practice than last week"), color: "#c0392b" };
  return { value: t("etwa gleich", "about the same"), sub: t("viel wie letzte Woche", "amount as last week"), color: "#4f46e5" };
}

export function ChildDashboard({ data }) {
  const { t, lang } = useLang();
  const TAGE = [t("Mo", "Mon"), t("Di", "Tue"), t("Mi", "Wed"), t("Do", "Thu"), t("Fr", "Fri"), t("Sa", "Sat"), t("So", "Sun")];
  const struggles = data.top_struggles || [];
  const daily = data.daily_activity || [0, 0, 0, 0, 0, 0, 0];
  const maxV = Math.max(...daily, 1);
  const trend = trendText(data.dranbleiben_delta || 0, t);
  // «Woche vom …»: Montag der angezeigten Woche, lokal formatiert
  const weekLabel = data.week_start
    ? new Date(data.week_start).toLocaleDateString(lang === "en" ? "en-GB" : "de-CH", { day: "numeric", month: "long" })
    : null;
  return (
    <>
      {/* Das Wichtigste zuerst: ein Satz in Klartext, aus echten Daten */}
      <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, padding: "16px 20px", fontSize: 15, lineHeight: 1.6, marginBottom: 20 }}>
        {summarySentence(data, t)}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16, marginBottom: 20 }} className="eltern-tiles">
        <Tile label={t("Gelöste Aufgaben", "Tasks solved")} value={data.solved_count} sub={t("diese Woche", "this week")} />
        <Tile label={t("Löst selbständig", "Solves independently")} value={data.autonomy_rate} unit="%" sub={t("der gelösten Aufgaben fast ohne Hilfe", "of solved tasks almost without help")} color="#1a7f3c" />
        <Tile label={t("Übungstage", "Practice days")} value={data.active_days} unit={t(" von 7", " of 7")} sub={t("diese Woche", "this week")} />
        <Tile label={t("Trend", "Trend")} value={trend.value} sub={trend.sub} color={trend.color} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 16 }} className="eltern-charts">
        <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, padding: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>{t("Themen mit viel Hilfebedarf", "Topics needing a lot of help")}</div>
          <div style={{ fontSize: 12, color: "#9aa0ab", marginBottom: 14 }}>{t("hier lohnt sich gemeinsames Üben", "practicing together pays off here")}</div>
          {struggles.length === 0 && <div style={{ fontSize: 13, color: "#9aa0ab" }}>{t("Kein Thema auffällig – läuft rund.", "No topic stands out – everything is going smoothly.")}</div>}
          {struggles.map((s) => {
            const chip = labelChip(s.label, t);
            // Sammel-Eintrag fuer Aufgaben ohne Themen-Zuordnung uebersetzen
            const topicLabel = s.topic === "Ohne Thema" ? t("Ohne Thema", "No topic") : s.topic;
            return (
              <div key={s.topic} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "9px 0", borderTop: "1px solid #f4f5f8" }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13.5, fontWeight: 600 }}>{topicLabel}</div>
                  {s.heavy != null && s.total ? (
                    <div style={{ fontSize: 11.5, color: "#9aa0ab" }}>
                      {s.heavy} {t("von", "of")} {s.total} {s.total === 1 ? t("Aufgabe brauchte", "task needed") : t("Aufgaben brauchten", "tasks needed")} {t("viel Hilfe", "a lot of help")}
                    </div>
                  ) : null}
                </div>
                <span style={{ flex: "0 0 auto", fontSize: 11, fontWeight: 700, borderRadius: 999, padding: "4px 11px", background: chip.bg, color: chip.fg }}>{chip.text}</span>
              </div>
            );
          })}
        </div>
        <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, padding: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>{t("An welchen Tagen geübt wurde", "Which days were practice days")}</div>
          <div style={{ fontSize: 12, color: "#9aa0ab", marginBottom: 12 }}>
            {weekLabel ? `${t("Woche vom", "Week of")} ${weekLabel} · ` : ""}{t("Zahl = gestartete Aufgaben", "number = tasks started")}
          </div>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 104 }}>
            {daily.map((v, i) => {
              const h = Math.max(Math.round((v / maxV) * 68), v > 0 ? 10 : 2);
              return (
                <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-end", gap: 4 }}>
                  {v > 0 && <span style={{ fontSize: 10.5, fontWeight: 700, color: v >= maxV ? "#4f46e5" : "#9aa0ab" }}>{v}</span>}
                  <div style={{ width: "100%", height: h, background: v > 0 ? (v >= maxV ? "#6366f1" : "#e7e8fb") : "#eef0f3", borderRadius: 6 }} />
                  <span style={{ fontSize: 10, color: "#9aa0ab" }}>{TAGE[i]}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 16, marginTop: 16 }} className="eltern-charts">
        {/* Konkrete Handlungsempfehlungen aus den Wochen-Zahlen */}
        <div style={{ background: "#f8f8ff", border: "1px solid #e0e2fb", borderRadius: 16, padding: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>{t("💡 So können Sie helfen", "💡 How you can help")}</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {helpTips(data, t).map((tip, i) => (
              <div key={i} style={{ display: "flex", gap: 9, fontSize: 13.5, lineHeight: 1.55, color: "#3a3d46" }}>
                <span style={{ color: "#4f46e5", fontWeight: 800 }}>→</span>
                <span>{tip}</span>
              </div>
            ))}
          </div>
        </div>
        {/* Verlauf ueber die letzten Wochen (nur mit genug Daten) */}
        {(data.history || []).length >= 2 ? (
          <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, padding: 20 }}>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>{t("Verlauf", "Trend over time")}</div>
            <div style={{ fontSize: 12, color: "#9aa0ab", marginBottom: 12 }}>{t("Gelöste Aufgaben pro Woche · Zahl = Selbständigkeit", "Tasks solved per week · number = independence")}</div>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 10, height: 104 }}>
              {[...data.history].reverse().map((w, i, arr) => {
                const maxSolved = Math.max(...arr.map((x) => x.solved_count), 1);
                const h = Math.max(Math.round((w.solved_count / maxSolved) * 62), w.solved_count > 0 ? 10 : 2);
                const isCurrent = i === arr.length - 1;
                const label = new Date(w.week_start).toLocaleDateString(lang === "en" ? "en-GB" : "de-CH", { day: "numeric", month: "numeric" });
                return (
                  <div key={w.week_start} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-end", gap: 4 }}>
                    <span style={{ fontSize: 10.5, fontWeight: 700, color: isCurrent ? "#4f46e5" : "#9aa0ab" }}>{w.solved_count > 0 ? `${w.autonomy_rate}%` : "–"}</span>
                    <div title={`${w.solved_count} ${t("gelöst", "solved")}`} style={{ width: "100%", height: h, background: w.solved_count > 0 ? (isCurrent ? "#6366f1" : "#e7e8fb") : "#eef0f3", borderRadius: 6 }} />
                    <span style={{ fontSize: 10, color: "#9aa0ab" }}>{label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div style={{ background: "#fff", border: "1px dashed #e7e8ee", borderRadius: 16, padding: 20, display: "grid", placeItems: "center", fontSize: 12.5, color: "#9aa0ab", textAlign: "center" }}>
            {t("Der Wochen-Verlauf erscheint hier, sobald zwei Übungswochen zusammengekommen sind.", "The weekly trend will appear here once there are two weeks of practice.")}
          </div>
        )}
      </div>
      <div style={{ marginTop: 16, fontSize: 12.5, color: "#9aa0ab" }}>
        {t("🔒 Sie sehen den groben Fortschritt – nie einzelne Nachrichten Ihres Kindes.", "🔒 You see overall progress – never your child's individual messages.")}
      </div>
    </>
  );
}

// SCHUELER-Seite: nur Eltern verbinden – kein Dashboard in der Kinder-App.
export default function Eltern() {
  const { t } = useLang();
  const { user } = useAuth();
  const [invite, setInvite] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.get("/api/parents/invite").then(setInvite).catch(() => setInvite(null));
  }, []);

  return (
    <div style={{ height: "100%", overflowY: "auto", background: "#fbfbfd", padding: "36px 40px" }}>
      <div style={{ maxWidth: 620, margin: "0 auto" }}>
        <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-.02em", marginBottom: 6 }}>{t("Eltern verbinden", "Connect parents")}</div>
        <div style={{ fontSize: 14, color: "#6b7280", marginBottom: 24, lineHeight: 1.55 }}>
          {t("Deine Eltern erstellen ein eigenes Eltern-Konto und geben dort diesen Code ein.", "Your parents create their own parent account and enter this code there.")}
        </div>

        {invite ? (
          <div style={{ background: "#eef0fe", border: "1px solid #dfe1fb", borderRadius: 18, padding: "22px 24px", textAlign: "center", marginBottom: 20 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#4f46e5", marginBottom: 10 }}>{t("DEIN EINLADUNGSCODE", "YOUR INVITE CODE")}</div>
            <div style={{ fontFamily: "ui-monospace, monospace", fontSize: 30, fontWeight: 800, letterSpacing: ".22em", color: "#1a1c22", background: "#fff", borderRadius: 12, padding: "12px 18px", border: "1px solid #dfe1fb", display: "inline-block", marginBottom: 14 }}>
              {invite.invite_code}
            </div>
            <div>
              <button
                onClick={() => { navigator.clipboard?.writeText(invite.invite_code); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
                className="btn-primary"
                style={{ padding: "10px 20px", borderRadius: 10, fontSize: 13, border: "none" }}
              >
                {copied ? t("kopiert ✓", "copied ✓") : t("Code kopieren", "Copy code")}
              </button>
            </div>
          </div>
        ) : (
          <div style={{ color: "#9aa0ab", fontSize: 14, marginBottom: 20 }}>{t("lädt …", "loading …")}</div>
        )}

        <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, padding: "18px 22px", marginBottom: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>{t("Das sehen deine Eltern", "What your parents can see")}</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 9, fontSize: 13.5, color: "#3a3d46" }}>
            <div><span style={{ color: "#1a7f3c", fontWeight: 700 }}>✓</span> {t("Wie viele Aufgaben du diese Woche gelöst hast", "How many tasks you solved this week")}</div>
            <div><span style={{ color: "#1a7f3c", fontWeight: 700 }}>✓</span> {t("Wie selbständig du arbeitest", "How independently you work")}</div>
            <div><span style={{ color: "#1a7f3c", fontWeight: 700 }}>✓</span> {t("An welchen Tagen du geübt hast", "Which days you practiced on")}</div>
            <div><span style={{ color: "#c0392b", fontWeight: 700 }}>✗</span> <b>{t("Nie", "Never")}</b> {t("deine Nachrichten mit dem Tutor – die bleiben privat", "your messages with the tutor – those stay private")}</div>
          </div>
        </div>

        <div style={{ fontSize: 12.5, color: "#9aa0ab", lineHeight: 1.55 }}>
          {t("Du kannst die Freigabe jederzeit ausschalten:", "You can turn off sharing at any time:")}{" "}
          <Link to="/app/einstellungen" style={{ color: "#4f46e5", fontWeight: 600 }}>{t("Einstellungen → Privatsphäre", "Settings → Privacy")}</Link>
        </div>

        {user?.is_admin && (
          <div style={{ background: "#fdf3e6", border: "1px solid #f2ddb8", borderRadius: 14, padding: "14px 18px", marginTop: 20, fontSize: 13 }}>
            <span style={{ color: "#a05c12", fontWeight: 700 }}>{t("Admin:", "Admin:")}</span>{" "}
            <Link to="/app/elternansicht" style={{ color: "#4f46e5", fontWeight: 700 }}>
              {t("👁 Elternansicht als Vorschau öffnen →", "👁 Open the parent view preview →")}
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
