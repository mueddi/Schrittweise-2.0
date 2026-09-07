import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { Tile } from "./Eltern.jsx";
import { useLang } from "../lib/i18n.jsx";

// Admin-Auswertung der KI-Kosten. Die Frage ist nicht nur «wie viel», sondern
// «woher»: welcher Aufruf-Typ, welcher Kostenbestandteil (Eingabe, Cache,
// Ausgabe), welches Modell, welche Aufgabe – und was daran auffaellig ist.
// Alle Zahlen kommen aus /api/admin/kosten; hier wird nur dargestellt.
export default function Kosten() {
  const { t } = useLang();
  const [tage, setTage] = useState(30);
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

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
  const pct = (v) => (v == null ? "–" : `${Math.round(v * 100)} %`);

  const pa = data?.pro_aufgabe;
  const g = data?.gesamt;

  // Die vier Bestandteile in fester Reihenfolge – so liest man in jeder
  // Tabelle dieselben Spalten.
  const BESTANDTEILE = [
    ["eingabe_chf", t("Eingabe neu", "Fresh input"), "#4f46e5"],
    ["cache_lesen_chf", t("Cache gelesen", "Cache read"), "#1a7f3c"],
    ["cache_schreiben_chf", t("Cache geschrieben", "Cache written"), "#c98a12"],
    ["ausgabe_chf", t("Ausgabe", "Output"), "#d9573a"],
  ];

  return (
    <div style={{ flex: 1, overflowY: "auto", background: "#fbfbfd" }}>
      <div style={{ maxWidth: 960, margin: "0 auto", padding: "28px 20px 60px" }}>
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
          {t("Was die KI-Aufrufe wirklich kosten und woher die Kosten kommen.", "What the AI calls actually cost and where the costs come from.")}
          {" "}
          {t("Anthropic rechnet in USD ab; Anzeige umgerechnet mit 1 USD ≈", "Anthropic bills in USD; displayed values converted at 1 USD ≈")} {data ? data.kurs_usd_chf.toLocaleString("de-CH") : "0.90"} CHF.
        </div>

        {err && (
          <div style={{ background: "#fdf0ee", border: "1px solid #f2c9c0", color: "#b3492f", borderRadius: 12, padding: "12px 16px", fontSize: 13, marginBottom: 16 }}>
            {err}
          </div>
        )}

        {loading && !data && <div style={{ fontSize: 13, color: "#9aa0ab" }}>{t("lädt …", "loading …")}</div>}

        {data && (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12, marginBottom: 20 }}>
              <Tile label={`${t("Gesamt", "Total")} (${data.zeitraum_tage} ${t("Tage", "days")})`} value={chf(g.kosten_chf)} unit=" CHF" sub={`${g.aufrufe} ${t("Aufrufe", "calls")}`} />
              <Tile label={t("Ø Kosten pro Aufgabe", "Avg. cost per task")} value={rp(pa.durchschnitt_rappen)} unit=" Rp." sub={`${pa.anzahl_aufgaben} ${t("Aufgaben · inkl. Foto", "tasks · photo included")} · Ø ${pa.chats_pro_aufgabe} ${t("Chat-Runden", "chat turns")}`} color="#4f46e5" />
              <Tile label={t("Teuerste Aufgabe", "Most expensive task")} value={rp(pa.max_rappen)} unit=" Rp." sub={t("günstigste", "cheapest") + `: ${rp(pa.min_rappen)} Rp.`} color="#d9573a" />
              <Tile label={t("Cache netto", "Cache, net")} value={chf(data.cache.netto_chf)} unit=" CHF" sub={`${t("gespart", "saved")} ${chf(data.cache.brutto_chf)} − ${t("Schreiben", "writes")} ${chf(data.cache.mehrkosten_chf)} · ${t("Quote", "hit rate")} ${pct(data.cache.quote)}`} color={data.cache.netto_chf >= 0 ? "#1a7f3c" : "#d9573a"} />
            </div>

            {g.aufrufe === 0 && (
              <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, padding: 20, fontSize: 13, color: "#6b7280" }}>
                {t("Noch keine Daten im gewählten Zeitraum. Die Erfassung läuft ab jetzt automatisch bei jedem Chat, jeder Foto-/Stift-Erkennung und jeder KI-Suche.", "No data yet in the selected period. From now on, tracking runs automatically for every chat, every photo/pen recognition and every AI search.")}
              </div>
            )}

            {data.hinweise.length > 0 && (
              <Card title={t("Was auffällt", "What stands out")}>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {data.hinweise.map((h, i) => (
                    <div key={i} style={{ display: "flex", gap: 10, fontSize: 13, lineHeight: 1.5, color: "#1a1c22" }}>
                      <span style={{ flexShrink: 0 }}>{h.art === "warn" ? "⚠️" : "•"}</span>
                      <span>{h.text}</span>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {g.aufrufe > 0 && (
              <Card title={t("Woher die Kosten kommen", "Where the costs come from")}>
                <div style={{ fontSize: 12.5, color: "#6b7280", marginBottom: 10, lineHeight: 1.5 }}>
                  {t(
                    "Jeder Aufruf besteht aus vier Posten: neu gelesene Eingabe (voller Preis), aus dem Cache gelesene Eingabe (ein Zehntel), in den Cache geschriebene Eingabe (1.25× bzw. 2× bei einer Stunde Frist) und die erzeugte Antwort (der teuerste Posten pro Token).",
                    "Every call has four parts: freshly read input (full price), input read from the cache (one tenth), input written to the cache (1.25×, or 2× with a one-hour lifetime) and the generated answer (the most expensive part per token)."
                  )}
                </div>
                <Anteile werte={data.anteile} bestandteile={BESTANDTEILE} chf={chf} pct={pct} />
              </Card>
            )}

            {data.nach_typ.length > 0 && (
              <Card title={t("Nach Typ", "By type")}>
                <table style={tableStyle}>
                  <thead>
                    <tr>
                      <Th align="left">{t("Typ", "Type")}</Th>
                      <Th>{t("Aufrufe", "Calls")}</Th>
                      <Th>{t("Ø pro Aufruf", "Avg. per call")}</Th>
                      <Th>{t("Anteil", "Share")}</Th>
                      {BESTANDTEILE.map(([k, label]) => <Th key={k}>{label}</Th>)}
                      <Th>{t("Kosten CHF", "Cost CHF")}</Th>
                      <Th>{t("Verrechnet", "Charged")}</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.nach_typ.map((r) => (
                      <tr key={r.typ}>
                        <Td align="left" strong>
                          {r.label}
                          <div style={{ fontSize: 11, color: "#9aa0ab", fontWeight: 400 }}>{r.modelle.join(", ")}</div>
                        </Td>
                        <Td>{tok(r.aufrufe)}</Td>
                        <Td>{rp(r.pro_aufruf_rappen)} Rp.</Td>
                        <Td>{pct(r.anteil)}</Td>
                        {BESTANDTEILE.map(([k]) => <Td key={k}>{chf(r[k])}</Td>)}
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
                      <Th>{t("Ø pro Aufruf", "Avg. per call")}</Th>
                      <Th>{t("Eingabe-Tokens", "Input tokens")}</Th>
                      <Th>{t("Cache gelesen", "Cache read")}</Th>
                      <Th>{t("Cache geschrieben", "Cache written")}</Th>
                      <Th>{t("Cache-Quote", "Cache hit rate")}</Th>
                      <Th>{t("Cache netto", "Cache, net")}</Th>
                      <Th>{t("Kosten CHF", "Cost CHF")}</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.nach_modell.map((r) => (
                      <tr key={r.modell}>
                        <Td align="left" strong>{r.modell}</Td>
                        <Td>{tok(r.aufrufe)}</Td>
                        <Td>{rp(r.pro_aufruf_rappen)} Rp.</Td>
                        <Td>{tok(r.input_tokens)}</Td>
                        <Td>{tok(r.cache_read_tokens)}</Td>
                        <Td>{tok(r.cache_write_tokens)}</Td>
                        <Td>{pct(r.cache_quote)}</Td>
                        <Td style={{ color: r.cache_netto_chf < 0 ? "#b3492f" : undefined }}>{chf(r.cache_netto_chf)}</Td>
                        <Td strong>{chf(r.kosten_chf)}</Td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div style={{ fontSize: 11.5, color: "#9aa0ab", marginTop: 8, lineHeight: 1.5 }}>
                  {t(
                    "Cache-Quote: Anteil der Eingabe-Tokens, die aus dem Cache kamen. Liegt sie tief, wird der Vorlauf (Prompt + Aufgabe) bei fast jedem Aufruf neu bezahlt.",
                    "Cache hit rate: share of input tokens served from the cache. If it is low, the prefix (prompt + task) is paid again on almost every call."
                  )}
                </div>
              </Card>
            )}

            {data.teuerste_aufgaben.length > 0 && (
              <Card title={t("Teuerste Aufgaben", "Most expensive tasks")}>
                <table style={tableStyle}>
                  <thead>
                    <tr>
                      <Th align="left">{t("Aufgabe", "Task")}</Th>
                      <Th>{t("Chat-Runden", "Chat turns")}</Th>
                      <Th>{t("Fotos", "Photos")}</Th>
                      <Th>{t("Kosten", "Cost")}</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.teuerste_aufgaben.map((r) => (
                      <tr key={r.exercise_id}>
                        <Td align="left">
                          <span style={{ color: "#9aa0ab", fontSize: 11 }}>#{r.exercise_id} </span>
                          {r.text || t("(nur Bild)", "(image only)")}
                          {r.von_admin && <span style={{ marginLeft: 6, fontSize: 11, color: "#9aa0ab" }}>{t("· dein Konto", "· your account")}</span>}
                        </Td>
                        <Td>{r.chats}</Td>
                        <Td>{r.fotos}</Td>
                        <Td strong>{rp(r.rappen)} Rp.</Td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            )}

            {g.aufrufe > 0 && (
              <Card title={t("Kosten und Einnahmen", "Costs and revenue")}>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
                  <Tile label={t("Verrechnete Aufrufe", "Charged calls")} value={g.verrechnete_aufrufe} sub={`${t("Kosten", "cost")} ${chf(g.kosten_verrechnet_chf)} CHF → ${tok(g.verrechnet_tokens)} Rp. ${t("verrechnet", "charged")}`} />
                  <Tile label={t("Marge auf verrechnete Aufrufe", "Margin on charged calls")} value={g.marge_ist != null ? `${g.marge_ist}×` : "–"} sub={`${t("Ziel", "target")} ${data.marge_soll}×`} color={g.marge_ist == null || g.marge_ist >= data.marge_soll ? "#1a7f3c" : "#d9573a"} />
                  <Tile label={t("Gratis-Aufrufe", "Free calls")} value={chf(g.kosten_gratis_chf)} unit=" CHF" sub={t("Betreiber-Konto und Schul-Plan – ohne Einnahmen", "operator account and school plan – no revenue")} color="#6b7280" />
                  <Tile label={t("Fotos ohne Aufgabe", "Photos without a task")} value={data.fotos_ohne_aufgabe.aufrufe} sub={`${chf(data.fotos_ohne_aufgabe.kosten_chf)} CHF – ${t("erkannt, aber nie zur Aufgabe geworden", "recognised but never turned into a task")}`} color="#c98a12" />
                </div>
              </Card>
            )}

            <div style={{ fontSize: 12, color: "#9aa0ab", marginTop: 16, lineHeight: 1.6 }}>
              {t(
                "Verrechnet wird nutzungsbasiert (1 Token = 1 Rp.) mit Sicherheitsmarge auf die echten Kosten; jeder Aufruf kostet mindestens 1 Rp. Die Marge oben misst nur die Aufrufe, für die tatsächlich verrechnet wurde – Gratis-Konten zählen nicht mit.",
                "Charging is usage-based (1 token = 1 Rp.) with a safety margin on actual costs; every call costs at least 1 Rp. The margin above measures only calls that were actually charged – free accounts are excluded."
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// Die vier Kostenbestandteile als Anteils-Zeilen: Betrag, Prozent und ein
// schlichter Balken – ohne Diagramm-Bibliothek.
function Anteile({ werte, bestandteile, chf, pct }) {
  const summe = bestandteile.reduce((s, [k]) => s + (werte[k] || 0), 0) || 1;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {bestandteile.map(([k, label, farbe]) => {
        const v = werte[k] || 0;
        return (
          <div key={k} style={{ display: "grid", gridTemplateColumns: "150px 1fr 90px 60px", alignItems: "center", gap: 10, fontSize: 13 }}>
            <span>{label}</span>
            <div style={{ background: "#f0f1f5", borderRadius: 6, height: 10, overflow: "hidden" }}>
              <div style={{ width: `${Math.round((v / summe) * 100)}%`, background: farbe, height: "100%" }} />
            </div>
            <span style={{ textAlign: "right", fontWeight: 600 }}>{chf(v)} CHF</span>
            <span style={{ textAlign: "right", color: "#6b7280" }}>{pct(v / summe)}</span>
          </div>
        );
      })}
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

const tableStyle = { width: "100%", borderCollapse: "collapse", fontSize: 13, minWidth: 560 };

function Th({ children, align = "right" }) {
  return (
    <th style={{ textAlign: align, padding: "6px 10px", fontSize: 11, fontWeight: 700, letterSpacing: ".05em", color: "#9aa0ab", borderBottom: "1px solid #eef0f3", whiteSpace: "nowrap" }}>
      {children}
    </th>
  );
}

function Td({ children, align = "right", strong = false, style = {} }) {
  return (
    <td style={{ textAlign: align, padding: "8px 10px", borderBottom: "1px solid #f4f5f8", fontWeight: strong ? 600 : 400, whiteSpace: "nowrap", ...style }}>
      {children}
    </td>
  );
}
