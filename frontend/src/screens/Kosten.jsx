import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { Tile } from "./Eltern.jsx";
import { useLang } from "../lib/i18n.jsx";

// Admin-Auswertung der KI-Kosten: was kostet eine Aufgabe im Schnitt,
// wo geht das Geld hin (Chat / Erkennung / Suche), welches Modell frisst wie viel.
export default function Kosten() {
  const { t, lang } = useLang();
  const [tage, setTage] = useState(30);
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [alarme, setAlarme] = useState([]);

  useEffect(() => {
    api.get("/api/admin/alarme").then(setAlarme).catch(() => setAlarme([]));
  }, []);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api
      .get(`/api/admin/kosten?tage=${tage}`)
      .then((d) => alive && (setData(d), setErr("")))
      .catch((e) => alive && setErr(e.message || t("Konnte die Auswertung nicht laden.", "Could not load the report.")))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [tage]); // eslint-disable-line react-hooks/exhaustive-deps

  const rp = (v) => (v == null ? "–" : v.toLocaleString("de-CH", { maximumFractionDigits: 2 }));
  const chf = (v) => (v == null ? "–" : v.toLocaleString("de-CH", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
  const tok = (v) => (v == null ? "–" : v.toLocaleString("de-CH"));

  const pa = data?.pro_aufgabe;

  return (
    <div style={{ flex: 1, overflowY: "auto", background: "#fbfbfd" }}>
      <div style={{ maxWidth: 860, margin: "0 auto", padding: "28px 20px 60px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 6 }}>
          <h1 style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-.02em", margin: 0 }}>{t("📊 KI-Kosten", "📊 AI Costs")}</h1>
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
          {t("Was die KI-Aufrufe wirklich kosten – zum Prüfen, ob die Paketpreise aufgehen.", "What the AI calls actually cost – to check whether the package prices add up.")}
          {" "}
          {t("Anthropic rechnet in USD ab; Anzeige umgerechnet mit 1 USD ≈", "Anthropic bills in USD; displayed values converted at 1 USD ≈")} {data ? data.kurs_usd_chf.toLocaleString("de-CH") : "0.90"} CHF.
        </div>

        {err && (
          <div style={{ background: "#fdf0ee", border: "1px solid #f2c9c0", color: "#b3492f", borderRadius: 12, padding: "12px 16px", fontSize: 13, marginBottom: 16 }}>
            {err}
          </div>
        )}

        {alarme.length > 0 && (
          <div style={{ background: "#fdf6f4", border: "1px solid #f2c9c0", borderRadius: 14, padding: 16, marginBottom: 20 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#b3492f", marginBottom: 8 }}>{t("⚠️ Letzte Störungen", "⚠️ Recent incidents")}</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {alarme.slice(0, 5).map((a, i) => (
                <div key={i} style={{ fontSize: 12.5, color: "#6b7280" }}>
                  <b style={{ color: "#1a1c22" }}>{a.label}</b>
                  {a.zeit ? ` · ${new Date(a.zeit).toLocaleString("de-CH")}` : ""}
                  {a.detail ? ` – ${a.detail.slice(0, 140)}` : ""}
                </div>
              ))}
            </div>
          </div>
        )}
        {loading && !data && <div style={{ fontSize: 13, color: "#9aa0ab" }}>{t("lädt …", "loading …")}</div>}

        {data && (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12, marginBottom: 24 }}>
              <Tile label={t("Ø Kosten pro Aufgabe", "Avg. cost per task")} value={rp(pa.durchschnitt_rappen)} unit=" Rp." sub={`${pa.anzahl_aufgaben} ${t("Aufgaben ausgewertet", "tasks evaluated")}`} color="#4f46e5" />
              <Tile label={t("Günstigste Aufgabe", "Cheapest task")} value={rp(pa.min_rappen)} unit=" Rp." sub={t("Summe aller Chat-Aufrufe", "Sum of all chat calls")} color="#1a7f3c" />
              <Tile label={t("Teuerste Aufgabe", "Most expensive task")} value={rp(pa.max_rappen)} unit=" Rp." sub={t("Summe aller Chat-Aufrufe", "Sum of all chat calls")} color="#d9573a" />
              <Tile label={`${t("Gesamt", "Total")} (${data.zeitraum_tage} ${t("Tage", "days")})`} value={chf(data.gesamt.kosten_chf)} unit=" CHF" sub={`${data.gesamt.aufrufe} ${t("Aufrufe", "calls")} · ${tok(data.gesamt.verrechnet_tokens ?? 0)} ${t("Rp. verrechnet", "Rp. charged")}`} />
            </div>

            {data.gesamt.aufrufe === 0 && (
              <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, padding: 20, fontSize: 13, color: "#6b7280" }}>
                {t("Noch keine Daten im gewählten Zeitraum. Die Erfassung läuft ab jetzt automatisch bei jedem Chat, jeder Foto-/Stift-Erkennung und jeder KI-Suche.", "No data yet in the selected period. From now on, tracking runs automatically for every chat, every photo/pen recognition and every AI search.")}
              </div>
            )}

            {data.nach_typ.length > 0 && (
              <Card title={t("Nach Typ", "By type")}>
                <table style={tableStyle}>
                  <thead>
                    <tr>
                      <Th align="left">{t("Typ", "Type")}</Th>
                      <Th>{t("Aufrufe", "Calls")}</Th>
                      <Th>{t("Input-Tokens", "Input tokens")}</Th>
                      <Th>{t("Output-Tokens", "Output tokens")}</Th>
                      <Th>{t("Cache (gelesen)", "Cache (read)")}</Th>
                      <Th>{t("Kosten CHF", "Cost CHF")}</Th>
                      <Th>{t("Verrechnet", "Charged")}</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.nach_typ.map((r) => (
                      <tr key={r.typ}>
                        <Td align="left" strong>{r.label}</Td>
                        <Td>{tok(r.aufrufe)}</Td>
                        <Td>{tok(r.input_tokens)}</Td>
                        <Td>{tok(r.output_tokens)}</Td>
                        <Td>{tok(r.cache_read_tokens)}</Td>
                        <Td strong>{chf(r.kosten_chf)}</Td>
                        <Td>{r.verrechnet_tokens != null ? `${tok(r.verrechnet_tokens)} Rp.` : "–"}</Td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            )}

            {data.nach_modell.length > 0 && (
              <Card title={t("Nach Modell", "By model")}>
                <table style={tableStyle}>
                  <thead>
                    <tr>
                      <Th align="left">{t("Modell", "Model")}</Th>
                      <Th>{t("Aufrufe", "Calls")}</Th>
                      <Th>{t("Kosten CHF", "Cost CHF")}</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.nach_modell.map((r) => (
                      <tr key={r.modell}>
                        <Td align="left" strong>{r.modell}</Td>
                        <Td>{tok(r.aufrufe)}</Td>
                        <Td strong>{chf(r.kosten_chf)}</Td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            )}

            <div style={{ fontSize: 12, color: "#9aa0ab", marginTop: 16, lineHeight: 1.6 }}>
              {t(
                "Zum Einordnen: Verrechnet wird nutzungsbasiert mit 3× Marge auf die echten Kosten (1 Token = 1 Rp.) – «Verrechnet» sollte langfristig ≈ 3× der Kosten-Spalte sein. Das starke Modell (Sonnet) ist rund 3× teurer als das Standard-Modell (Haiku).",
                "For context: charging is usage-based with a 3× margin on actual costs (1 token = 1 Rp.) – \"Charged\" should over time be ≈ 3× the cost column. The strong model (Sonnet) is about 3× more expensive than the standard model (Haiku)."
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function Card({ title, children }) {
  return (
    <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, padding: 18, marginBottom: 16 }}>
      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12 }}>{title}</div>
      <div style={{ overflowX: "auto" }}>{children}</div>
    </div>
  );
}

const tableStyle = { width: "100%", borderCollapse: "collapse", fontSize: 13, minWidth: 480 };

function Th({ children, align = "right" }) {
  return (
    <th style={{ textAlign: align, padding: "6px 10px", fontSize: 11, fontWeight: 700, letterSpacing: ".05em", color: "#9aa0ab", borderBottom: "1px solid #eef0f3", whiteSpace: "nowrap" }}>
      {children}
    </th>
  );
}

function Td({ children, align = "right", strong = false }) {
  return (
    <td style={{ textAlign: align, padding: "8px 10px", borderBottom: "1px solid #f4f5f8", fontWeight: strong ? 600 : 400, whiteSpace: "nowrap" }}>
      {children}
    </td>
  );
}
