import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";
import { useShell } from "./AppShell.jsx";
import { useLang } from "../lib/i18n.jsx";

// Probeprüfung starten – mit dem Preis VOR dem Klick. Eine Prüfung kostet ein
// Vielfaches eines Chat-Turns; bei 50 Gratis-Tokens im Monat darf das niemand
// aus Versehen ausgeben.
const KASTEN = { background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, padding: 18 };

export default function PruefungStart({ topicId }) {
  const { t } = useLang();
  const nav = useNavigate();
  const shell = useShell();
  const [vorschau, setVorschau] = useState(null);
  const [alte, setAlte] = useState([]);
  const [busy, setBusy] = useState(false);
  const [fehler, setFehler] = useState("");

  const laden = useCallback(async () => {
    try {
      const [v, liste] = await Promise.all([
        api.post(`/api/topics/${topicId}/pruefung/vorschau`),
        api.get(`/api/topics/${topicId}/pruefungen`),
      ]);
      setVorschau(v);
      setAlte(liste);
    } catch {
      setVorschau(null);
    }
  }, [topicId]);
  useEffect(() => { laden(); }, [laden]);

  async function starten() {
    if (!window.confirm(
      t(`Diese Probeprüfung kostet ungefähr ${vorschau.kosten_rappen} Tokens von deinen ${vorschau.guthaben} übrigen. Jetzt starten?`,
        `This practice test costs about ${vorschau.kosten_rappen} tokens of your ${vorschau.guthaben} remaining. Start now?`))) return;
    setBusy(true);
    setFehler("");
    try {
      const p = await api.post(`/api/topics/${topicId}/pruefung`);
      shell.reloadQuota?.();
      nav(`/app/pruefung/${p.id}`);
    } catch (e) {
      setFehler(e?.message || t("Das hat nicht geklappt.", "That didn't work."));
      setBusy(false);
    }
  }

  if (!vorschau) return null;
  const offene = alte.find((p) => p.status === "offen");

  return (
    <div style={{ ...KASTEN, marginBottom: 18 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700 }}>{t("Probeprüfung", "Practice test")}</div>
          <div style={{ fontSize: 13, color: "#6b7280", marginTop: 3 }}>
            {vorschau.moeglich
              ? t("Aus deinen Lernzielen und den Aufgaben dieses Themas – ohne Tutor, wie eine echte Prüfung.",
                  "Built from your goals and this topic's tasks – no tutor, just like a real test.")
              : vorschau.grund}
          </div>
        </div>
        {offene ? (
          <button onClick={() => nav(`/app/pruefung/${offene.id}`)} className="btn-primary"
                  style={{ padding: "10px 16px", borderRadius: 11, fontSize: 13, border: "none" }}>
            {t("Angefangene Prüfung fortsetzen", "Continue your test")}
          </button>
        ) : vorschau.moeglich ? (
          <button onClick={starten} disabled={busy} className="btn-primary"
                  style={{ padding: "10px 16px", borderRadius: 11, fontSize: 13, border: "none", opacity: busy ? 0.6 : 1 }}>
            {busy ? t("wird erstellt …", "creating …") : t(`Prüfung starten · ca. ${vorschau.kosten_rappen} Tokens`, `Start test · approx. ${vorschau.kosten_rappen} tokens`)}
          </button>
        ) : null}
      </div>
      {/* Ohne diesen Satz sieht ein Wartevorgang wie «tut nichts» aus – die
          KI schreibt acht Aufgaben, das dauert ein paar Sekunden. */}
      {busy && (
        <div style={{ fontSize: 12.5, color: "#6b7280", marginTop: 10 }}>
          {t("Die Aufgaben werden gerade geschrieben – das dauert ein paar Sekunden. Bitte die Seite nicht neu laden.",
             "Your tasks are being written – this takes a few seconds. Please don't reload the page.")}
        </div>
      )}
      {fehler && (
        <div style={{ marginTop: 10, background: "#fdecec", border: "1px solid #f3c1bc", borderRadius: 10, padding: "9px 12px", fontSize: 13, color: "#c0392b" }}>
          {fehler}
        </div>
      )}

      {alte.filter((p) => p.status === "bewertet").length > 0 && (
        <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 6 }}>
          {alte.filter((p) => p.status === "bewertet").map((p) => (
            <div key={p.id} onClick={() => nav(`/app/pruefung/${p.id}`)}
                 style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13, cursor: "pointer" }}>
              <span style={{ width: 38, fontWeight: 800, color: p.grade_value >= 4 ? "#1a7f3c" : "#c0392b" }}>
                {p.grade_value?.toFixed(1)}
              </span>
              <span style={{ color: "#9aa0ab" }}>{String(p.created_at).slice(0, 10)}</span>
              <span style={{ color: "#6b7280" }}>{p.richtig}/{p.total} {t("richtig", "correct")}</span>
              <span style={{ marginLeft: "auto", color: "#b6bcc6" }}>›</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
