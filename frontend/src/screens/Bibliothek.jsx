import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";
import { useLang, GRADE_KEYS, gradeLabel, gradeShort } from "../lib/i18n.jsx";
import { useDialog } from "../lib/dialog.jsx";
import MathText from "../lib/MathText.jsx";

// Aufgaben-Bibliothek: fertige Aufgaben, die ein Schueler mit einem Klick im
// Tutor startet. Der Betreiber fuellt sie einzeln, als Liste oder per KI.

// Stabile Farbe pro Themen-Name (Themen sind frei benennbar)
const PALETTE = ["#6366f1", "#e0993a", "#1a7f3c", "#c0392b", "#0e7490", "#7c3aed", "#b45309"];
function colorFor(name) {
  let h = 0;
  for (const c of name || "") h = (h * 31 + c.charCodeAt(0)) % 9973;
  return PALETTE[h % PALETTE.length];
}

// users.grade_level (auch Alt-Werte wie «Gymnasium 1./2.») -> Bibliotheks-Schluessel
function klassenSchluessel(gradeLevel) {
  const g = (gradeLevel || "").toLowerCase();
  if (g.includes("gym")) return "gymnasium";
  if (g.includes("mittel")) return "mittelstufe";
  return "oberstufe";
}

const chip = (aktiv) => ({
  fontSize: 12, fontWeight: 600, borderRadius: 999, padding: "5px 12px", cursor: "pointer",
  background: aktiv ? "#eef0fe" : "#fff", color: aktiv ? "#4f46e5" : "#6b7280",
  border: `1px solid ${aktiv ? "#c9ccf6" : "#e7e8ee"}`,
});
const labelStyle = { fontSize: 12, fontWeight: 600, color: "#6b7280", display: "block", marginBottom: 5 };
const inputStyle = { width: "100%", border: "1px solid #d2d4dd", borderRadius: 10, padding: "9px 12px", fontSize: 13, outline: "none", background: "#fff", boxSizing: "border-box" };
const noteStyle = (fehler) => ({ fontSize: 13, borderRadius: 10, padding: "9px 12px", background: fehler ? "#fdecec" : "#e8f6ec", color: fehler ? "#c0392b" : "#1a7f3c", border: `1px solid ${fehler ? "#f5cccc" : "#cde7d6"}` });

function ChipRow({ label, options, value, onChange }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
      <span style={{ fontSize: 11, fontWeight: 700, color: "#9aa0ab", width: 88, flex: "0 0 88px" }}>{label}</span>
      {options.map(([val, lbl]) => (
        <button key={val} onClick={() => onChange(val)} style={chip(value === val)}>{lbl}</button>
      ))}
    </div>
  );
}

export default function Bibliothek() {
  const { user } = useAuth();
  const { t, lang } = useLang();
  const dialog = useDialog();
  const nav = useNavigate();
  const istAdmin = !!user?.is_admin;
  const [q, setQ] = useState("");
  // Schueler sehen zuerst ihre eigene Stufe; der Betreiber alles.
  const [grade, setGrade] = useState(istAdmin ? "" : klassenSchluessel(user?.grade_level));
  const [category, setCategory] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [items, setItems] = useState(null); // null = laedt
  const [topics, setTopics] = useState([]);
  const [error, setError] = useState(null);
  const [adminOpen, setAdminOpen] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [editId, setEditId] = useState(null);

  const GRADES = [["", t("Alle", "All")], ...GRADE_KEYS.map((k) => [k, gradeShort(k, lang)])];
  const DIFFICULTIES = [["", t("Alle", "All")], ["leicht", t("Leicht", "Easy")], ["mittel", t("Mittel", "Medium")], ["schwer", t("Schwer", "Hard")]];
  const diffLabel = { leicht: t("leicht", "easy"), mittel: t("mittel", "medium"), schwer: t("schwer", "hard") };

  const loadTopics = useCallback(async () => {
    try {
      setTopics(await api.get("/api/library/topics"));
    } catch {
      setTopics([]);
    }
  }, []);

  const load = useCallback(async () => {
    setError(null);
    try {
      const params = new URLSearchParams();
      if (q.trim()) params.set("q", q.trim());
      if (grade) params.set("grade", grade);
      if (category) params.set("category", category);
      if (difficulty) params.set("difficulty", difficulty);
      setItems(await api.get(`/api/library${params.size ? `?${params}` : ""}`));
    } catch (e) {
      setError(e.message);
      setItems([]);
    }
  }, [q, grade, category, difficulty]);

  useEffect(() => {
    loadTopics();
  }, [loadTopics]);
  useEffect(() => {
    const id = setTimeout(load, q ? 250 : 0); // Tippen entprellen
    return () => clearTimeout(id);
  }, [load, q]);

  const refresh = () => {
    loadTopics();
    load();
  };

  async function start(item) {
    setBusyId(item.id);
    setError(null);
    try {
      const st = await api.post(`/api/library/${item.id}/start`, {});
      nav(`/app/lernen/${st.attempt.id}`);
    } catch (e) {
      setError(e.message);
      setBusyId(null);
    }
  }

  async function remove(item) {
    const ja = await dialog.bestaetigen({
      titel: t("Aufgabe aus der Bibliothek löschen?", "Delete task from the library?"),
      text: t("Schüler, die sie schon gestartet haben, behalten ihre Kopie.", "Students who already started it keep their copy."),
      bestaetigen: t("Löschen", "Delete"),
      gefahr: true,
    });
    if (!ja) return;
    try {
      await api.del(`/api/library/${item.id}`);
      refresh();
    } catch (e) {
      setError(e.message);
    }
  }

  const gefiltert = q || grade || category || difficulty;

  return (
    <div style={{ height: "100%", overflowY: "auto", background: "#f6f7fb" }}>
      <div style={{ maxWidth: 860, margin: "0 auto", padding: "26px 24px 60px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 4 }}>
          <div>
            <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-.02em" }}>{t("📚 Aufgaben zum Üben", "📚 Practice tasks")}</div>
            <div style={{ fontSize: 13, color: "#6b7280" }}>{t("Such dir eine Aufgabe aus – Kniff hilft dir Schritt für Schritt.", "Pick a task – Kniff helps you step by step.")}</div>
          </div>
          {istAdmin && (
            <button onClick={() => setAdminOpen((v) => !v)} className="btn-ghost" style={{ fontSize: 12, padding: "9px 14px", borderRadius: 999, whiteSpace: "nowrap" }}>
              {adminOpen ? t("✕ Verwalten schliessen", "✕ Close manage") : t("⚙ Verwalten", "⚙ Manage")}
            </button>
          )}
        </div>

        {istAdmin && adminOpen && (
          <>
            <TopicManager topics={topics} onChanged={refresh} />
            <AufgabenForm topics={topics} onDone={refresh} />
            <KiErzeugung topics={topics} onDone={refresh} />
          </>
        )}

        <div style={{ display: "flex", alignItems: "center", gap: 8, background: "#fff", border: "1px solid #d2d4dd", borderRadius: 12, padding: "10px 14px", margin: "18px 0 12px" }}>
          <span style={{ color: "#b6bcc6" }}>🔎</span>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("Suchen, z.B. Bruch, Prozent, Gleichung …", "Search, e.g. fraction, percent, equation …")} style={{ flex: 1, border: "none", outline: "none", fontSize: 13, background: "transparent" }} />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 20 }}>
          <ChipRow label={t("THEMA", "TOPIC")} options={[["", t("Alle", "All")], ...topics.map((tp) => [tp.name, `${tp.name} (${tp.doc_count})`])]} value={category} onChange={setCategory} />
          <ChipRow label={t("STUFE", "LEVEL")} options={GRADES} value={grade} onChange={setGrade} />
          <ChipRow label={t("SCHWIERIGKEIT", "DIFFICULTY")} options={DIFFICULTIES} value={difficulty} onChange={setDifficulty} />
        </div>

        {error && <div style={noteStyle(true)}>{error}</div>}

        {items === null ? (
          <div style={{ color: "#9aa0ab", fontSize: 14, textAlign: "center", padding: 40 }}>{t("lädt …", "loading …")}</div>
        ) : items.length === 0 ? (
          <div style={{ textAlign: "center", padding: "48px 20px", color: "#6b7280" }}>
            <div style={{ fontSize: 30, marginBottom: 10 }}>🗂️</div>
            <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>
              {gefiltert ? t("Keine Aufgaben gefunden", "No tasks found") : t("Hier kommen bald Aufgaben hin.", "Tasks are coming here soon.")}
            </div>
            <div style={{ fontSize: 13 }}>
              {gefiltert ? t("Probier andere Filter.", "Try other filters.") : t("Bis dahin: eigene Aufgabe eintippen oder fotografieren unter «Lernen».", "Until then: type or photograph your own task under \"Learn\".")}
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {items.map((a) => (
              <div key={a.id} style={{ background: "#fff", border: `1px solid ${a.status === "geloest" ? "#cde7d6" : "#e7e8ee"}`, borderRadius: 14, padding: "16px 18px" }}>
                {editId === a.id ? (
                  <BearbeitenForm item={a} topics={topics} onDone={() => { setEditId(null); refresh(); }} onCancel={() => setEditId(null)} />
                ) : (
                  <div style={{ display: "flex", gap: 14, alignItems: "flex-start", flexWrap: "wrap" }}>
                    <div style={{ flex: 1, minWidth: 240 }}>
                      <div style={{ fontSize: 15, lineHeight: 1.55, marginBottom: 8 }}><MathText text={a.text} /></div>
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                        <span style={{ fontSize: 11, fontWeight: 700, borderRadius: 999, padding: "3px 10px", background: `${colorFor(a.category)}18`, color: colorFor(a.category) }}>{a.category}</span>
                        {a.grade_levels.map((g) => (
                          <span key={g} style={{ fontSize: 11, fontWeight: 600, borderRadius: 999, padding: "3px 10px", background: "#f1f2f6", color: "#6b7280" }}>{gradeShort(g, lang)}</span>
                        ))}
                        <span style={{ fontSize: 11, fontWeight: 600, borderRadius: 999, padding: "3px 10px", background: "#f1f2f6", color: "#6b7280" }}>{diffLabel[a.difficulty] || a.difficulty}</span>
                        {a.status === "geloest" && <span style={{ fontSize: 11, fontWeight: 700, color: "#1a7f3c" }}>✓ {t("gelöst", "solved")}</span>}
                        {a.status === "offen" && <span style={{ fontSize: 11, fontWeight: 700, color: "#c98a12" }}>{t("angefangen", "started")}</span>}
                        {istAdmin && (
                          <span style={{ fontSize: 11, color: "#b6bcc6" }}>
                            {a.math_expression ? t("prüfbar", "verifiable") : t("nicht prüfbar", "not verifiable")}{a.source ? ` · ${a.source}` : ""}
                          </span>
                        )}
                      </div>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "stretch" }}>
                      {a.status === "offen" ? (
                        <>
                          <button onClick={() => nav(`/app/lernen/${a.attempt_id}`)} className="btn-primary" style={{ fontSize: 12, borderRadius: 10, padding: "9px 16px", whiteSpace: "nowrap" }}>{t("Weiter →", "Continue →")}</button>
                          <button onClick={() => start(a)} disabled={busyId === a.id} className="btn-ghost" style={{ fontSize: 11, borderRadius: 10, padding: "7px 12px" }}>{t("Neu starten", "Start over")}</button>
                        </>
                      ) : (
                        <button onClick={() => start(a)} disabled={busyId === a.id} className="btn-primary" style={{ fontSize: 12, borderRadius: 10, padding: "9px 16px", whiteSpace: "nowrap", opacity: busyId === a.id ? 0.6 : 1 }}>
                          {busyId === a.id ? t("startet …", "starting …") : a.status === "geloest" ? t("Nochmal lösen", "Solve again") : t("Mit Kniff lösen →", "Solve with Kniff →")}
                        </button>
                      )}
                      {istAdmin && (
                        <div style={{ display: "flex", gap: 6 }}>
                          <button onClick={() => setEditId(a.id)} style={{ flex: 1, fontSize: 11, border: "1px solid #e7e8ee", background: "#fff", borderRadius: 10, padding: "7px 10px", cursor: "pointer" }}>{t("Bearbeiten", "Edit")}</button>
                          <button onClick={() => remove(a)} style={{ flex: 1, fontSize: 11, border: "1px solid #f5cccc", background: "#fff", color: "#c0392b", borderRadius: 10, padding: "7px 10px", cursor: "pointer" }}>{t("Löschen", "Delete")}</button>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Klassenstufen-Auswahl (Mehrfach) fuer die Betreiber-Formulare
function StufenWahl({ grades, onToggle }) {
  const { lang } = useLang();
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
      {GRADE_KEYS.map((g) => (
        <button type="button" key={g} onClick={() => onToggle(g)} style={{ ...chip(grades.includes(g)), padding: "7px 12px" }}>{gradeLabel(g, lang)}</button>
      ))}
    </div>
  );
}

function ThemaWahl({ topics, value, onChange }) {
  const { t } = useLang();
  return (
    <div>
      <label style={labelStyle}>{t("Thema", "Topic")}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)} style={inputStyle}>
        <option value="">{t("– wählen –", "– select –")}</option>
        {topics.map((tp) => <option key={tp.id} value={tp.name}>{tp.name}</option>)}
      </select>
      {topics.length === 0 && <div style={{ fontSize: 11, color: "#c0392b", marginTop: 4 }}>{t("Noch keine Themen – leg zuerst oben eines an.", "No topics yet – create one above first.")}</div>}
    </div>
  );
}

function SchwierigkeitWahl({ value, onChange }) {
  const { t } = useLang();
  return (
    <div>
      <label style={labelStyle}>{t("Schwierigkeit", "Difficulty")}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)} style={inputStyle}>
        <option value="leicht">{t("Leicht", "Easy")}</option>
        <option value="mittel">{t("Mittel", "Medium")}</option>
        <option value="schwer">{t("Schwer", "Hard")}</option>
      </select>
    </div>
  );
}

// Zeilen «Aufgabe | Ausdruck» (Ausdruck optional) in Eintraege verwandeln
function zeilenParsen(text) {
  return text.split("\n").map((z) => z.trim()).filter(Boolean).map((z) => {
    const [aufgabe, ausdruck] = z.split("|").map((s) => s.trim());
    return { text: aufgabe, math_expression: ausdruck || null };
  });
}

function AufgabenForm({ topics, onDone }) {
  const { t } = useLang();
  const [text, setText] = useState("");
  const [category, setCategory] = useState("");
  const [grades, setGrades] = useState(["oberstufe"]);
  const [difficulty, setDifficulty] = useState("mittel");
  const [source, setSource] = useState("eigene");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(null);

  const toggle = (g) => setGrades((p) => (p.includes(g) ? p.filter((x) => x !== g) : [...p, g]));

  async function submit(e) {
    e.preventDefault();
    const eintraege = zeilenParsen(text);
    if (eintraege.length === 0) return setNote({ fehler: true, text: t("Bitte mindestens eine Aufgabe eingeben.", "Please enter at least one task.") });
    if (!category) return setNote({ fehler: true, text: t("Bitte ein Thema wählen.", "Please select a topic.") });
    if (grades.length === 0) return setNote({ fehler: true, text: t("Bitte mindestens eine Klassenstufe wählen.", "Please select at least one level.") });
    setBusy(true);
    setNote(null);
    try {
      const aufgaben = eintraege.map((x) => ({ ...x, category, grade_levels: grades, difficulty, source }));
      const res = await api.post("/api/library/import", { aufgaben });
      setNote({ fehler: false, text: t(`${res.length} Aufgabe(n) gespeichert. ✓`, `${res.length} task(s) saved. ✓`) });
      setText("");
      onDone();
    } catch (e2) {
      setNote({ fehler: true, text: e2.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} style={{ background: "#fff", border: "1px solid #e0e2fb", borderRadius: 14, padding: 18, marginTop: 14, display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ fontSize: 14, fontWeight: 800 }}>{t("Aufgaben eintragen", "Add tasks")}</div>
      <div style={{ fontSize: 12, color: "#9aa0ab" }}>
        {t("Eine Aufgabe pro Zeile. Optional nach einem senkrechten Strich der Prüfausdruck, z.B. «Löse nach x auf: 3x + 5 = 20 | 3x + 5 = 20». Ohne Ausdruck versucht die App, ihn aus dem Text zu lesen; ist keiner erkennbar, beurteilt der Tutor selbst.",
           "One task per line. Optionally the verification expression after a vertical bar, e.g. \"Solve for x: 3x + 5 = 20 | 3x + 5 = 20\". Without it the app tries to read one from the text; if none is found, the tutor judges by itself.")}
      </div>
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={5} placeholder={t("Wie viel sind 25 % von 240 Franken? | 0.25 * 240\nKürze den Bruch 12/18.", "What is 25% of 240 francs? | 0.25 * 240\nSimplify the fraction 12/18.")} style={{ ...inputStyle, resize: "vertical", fontFamily: "inherit" }} />
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
        <ThemaWahl topics={topics} value={category} onChange={setCategory} />
        <div>
          <label style={labelStyle}>{t("Klassenstufen", "Levels")}</label>
          <StufenWahl grades={grades} onToggle={toggle} />
        </div>
        <SchwierigkeitWahl value={difficulty} onChange={setDifficulty} />
        <div>
          <label style={labelStyle}>{t("Quelle / Lizenz", "Source / licence")}</label>
          <input value={source} onChange={(e) => setSource(e.target.value)} placeholder="eigene · Serlo, CC BY-SA 4.0" style={inputStyle} />
        </div>
      </div>
      {note && <div style={noteStyle(note.fehler)}>{note.text}</div>}
      <button type="submit" disabled={busy} className="btn-primary" style={{ alignSelf: "flex-start", borderRadius: 10, padding: "10px 20px", fontSize: 13, opacity: busy ? 0.6 : 1 }}>
        {busy ? t("speichert …", "saving …") : t("Speichern", "Save")}
      </button>
    </form>
  );
}

function BearbeitenForm({ item, topics, onDone, onCancel }) {
  const { t } = useLang();
  const [text, setText] = useState(item.text);
  const [expr, setExpr] = useState(item.math_expression || "");
  const [category, setCategory] = useState(item.category);
  const [grades, setGrades] = useState(item.grade_levels);
  const [difficulty, setDifficulty] = useState(item.difficulty);
  const [source, setSource] = useState(item.source || "");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(null);
  const toggle = (g) => setGrades((p) => (p.includes(g) ? p.filter((x) => x !== g) : [...p, g]));

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setNote(null);
    try {
      await api.patch(`/api/library/${item.id}`, { text, math_expression: expr, category, grade_levels: grades, difficulty, source });
      onDone();
    } catch (e2) {
      setNote(e2.message);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} style={{ ...inputStyle, resize: "vertical", fontFamily: "inherit" }} />
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <label style={labelStyle}>{t("Prüfausdruck (leer = aus dem Text lesen)", "Verification expression (empty = read from text)")}</label>
          <input value={expr} onChange={(e) => setExpr(e.target.value)} style={inputStyle} />
        </div>
        <ThemaWahl topics={topics} value={category} onChange={setCategory} />
        <SchwierigkeitWahl value={difficulty} onChange={setDifficulty} />
        <div>
          <label style={labelStyle}>{t("Quelle / Lizenz", "Source / licence")}</label>
          <input value={source} onChange={(e) => setSource(e.target.value)} style={inputStyle} />
        </div>
      </div>
      <StufenWahl grades={grades} onToggle={toggle} />
      {note && <div style={noteStyle(true)}>{note}</div>}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" disabled={busy} className="btn-primary" style={{ borderRadius: 10, padding: "9px 16px", fontSize: 12 }}>{t("Speichern", "Save")}</button>
        <button type="button" onClick={onCancel} className="btn-ghost" style={{ borderRadius: 10, padding: "9px 16px", fontSize: 12 }}>{t("Abbrechen", "Cancel")}</button>
      </div>
    </form>
  );
}

function KiErzeugung({ topics, onDone }) {
  const { t, lang } = useLang();
  const [category, setCategory] = useState("");
  const [grade, setGrade] = useState("oberstufe");
  const [difficulty, setDifficulty] = useState("mittel");
  const [lernziel, setLernziel] = useState("");
  const [anzahl, setAnzahl] = useState(6);
  const [vorschau, setVorschau] = useState(null); // [{...aufgabe, gewaehlt}]
  const [kosten, setKosten] = useState(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(null);

  async function erzeugen(e) {
    e.preventDefault();
    if (!category) return setNote({ fehler: true, text: t("Bitte ein Thema wählen.", "Please select a topic.") });
    if (lernziel.trim().length < 3) return setNote({ fehler: true, text: t("Bitte beschreiben, was geübt werden soll.", "Please describe what should be practised.") });
    setBusy(true);
    setNote(null);
    setVorschau(null);
    try {
      const res = await api.post("/api/library/generieren", { category, grade_level: grade, difficulty, lernziel: lernziel.trim(), anzahl: Number(anzahl) });
      setVorschau(res.aufgaben.map((a) => ({ ...a, gewaehlt: true })));
      setKosten(res.kosten_rappen);
    } catch (e2) {
      setNote({ fehler: true, text: e2.message });
    } finally {
      setBusy(false);
    }
  }

  async function uebernehmen() {
    const gewaehlt = vorschau.filter((a) => a.gewaehlt).map(({ gewaehlt: _g, ...a }) => a);
    if (gewaehlt.length === 0) return;
    setBusy(true);
    try {
      const res = await api.post("/api/library/import", { aufgaben: gewaehlt });
      setNote({ fehler: false, text: t(`${res.length} Aufgabe(n) übernommen. ✓`, `${res.length} task(s) added. ✓`) });
      setVorschau(null);
      onDone();
    } catch (e2) {
      setNote({ fehler: true, text: e2.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ background: "#fff", border: "1px solid #e0e2fb", borderRadius: 14, padding: 18, marginTop: 14, display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ fontSize: 14, fontWeight: 800 }}>{t("Mit KI erzeugen", "Generate with AI")}</div>
      <div style={{ fontSize: 12, color: "#9aa0ab" }}>
        {t("Die KI schlägt Aufgaben vor, du liest sie durch und übernimmst, was passt. Gespeichert wird nichts, bevor du auf «Übernehmen» klickst. Kosten: unter einem Rappen pro Aufgabe, auf dein Konto.",
           "The AI proposes tasks, you read them and keep what fits. Nothing is saved before you click \"Add\". Cost: under one Rappen per task, on your account.")}
      </div>
      <form onSubmit={erzeugen} style={{ display: "flex", gap: 14, flexWrap: "wrap", alignItems: "flex-end" }}>
        <ThemaWahl topics={topics} value={category} onChange={setCategory} />
        <div>
          <label style={labelStyle}>{t("Klassenstufe", "Level")}</label>
          <select value={grade} onChange={(e) => setGrade(e.target.value)} style={inputStyle}>
            {GRADE_KEYS.map((g) => <option key={g} value={g}>{gradeLabel(g, lang)}</option>)}
          </select>
        </div>
        <SchwierigkeitWahl value={difficulty} onChange={setDifficulty} />
        <div>
          <label style={labelStyle}>{t("Anzahl", "Count")}</label>
          <input type="number" min={1} max={12} value={anzahl} onChange={(e) => setAnzahl(e.target.value)} style={{ ...inputStyle, width: 80 }} />
        </div>
        <div style={{ flex: "1 1 100%" }}>
          <label style={labelStyle}>{t("Was soll geübt werden? (ein Lernziel oder eine kurze Beschreibung)", "What should be practised? (a learning goal or a short description)")}</label>
          <input value={lernziel} onChange={(e) => setLernziel(e.target.value)} placeholder={t("z.B. Rabatt in Franken berechnen, wenn Preis und Prozentsatz gegeben sind", "e.g. calculate the discount in francs when price and percentage are given")} style={inputStyle} />
        </div>
        <button type="submit" disabled={busy} className="btn-primary" style={{ borderRadius: 10, padding: "10px 20px", fontSize: 13, opacity: busy ? 0.6 : 1 }}>
          {busy && !vorschau ? t("erzeugt …", "generating …") : t("Vorschau erzeugen", "Generate preview")}
        </button>
      </form>
      {note && <div style={noteStyle(note.fehler)}>{note.text}</div>}
      {vorschau && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ fontSize: 12, color: "#6b7280" }}>{t(`${vorschau.length} Vorschläge · ${kosten} Rp. KI-Kosten`, `${vorschau.length} proposals · ${kosten} Rp. AI cost`)}</div>
          {vorschau.map((a, i) => (
            <label key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start", background: "#fbfbfd", border: "1px solid #eef0f3", borderRadius: 10, padding: "10px 12px", cursor: "pointer" }}>
              <input type="checkbox" checked={a.gewaehlt} onChange={() => setVorschau((v) => v.map((x, j) => (j === i ? { ...x, gewaehlt: !x.gewaehlt } : x)))} style={{ marginTop: 3 }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, lineHeight: 1.5 }}><MathText text={a.text} /></div>
                <div style={{ fontSize: 11, color: "#9aa0ab", marginTop: 3 }}>{a.math_expression ? `${t("prüfbar", "verifiable")}: ${a.math_expression}` : t("nicht prüfbar – der Tutor beurteilt selbst", "not verifiable – the tutor judges by itself")}</div>
              </div>
            </label>
          ))}
          <button type="button" onClick={uebernehmen} disabled={busy || !vorschau.some((a) => a.gewaehlt)} className="btn-primary" style={{ alignSelf: "flex-start", borderRadius: 10, padding: "10px 20px", fontSize: 13 }}>
            {t(`${vorschau.filter((a) => a.gewaehlt).length} übernehmen`, `Add ${vorschau.filter((a) => a.gewaehlt).length}`)}
          </button>
        </div>
      )}
    </div>
  );
}

function TopicManager({ topics, onChanged }) {
  const { t } = useLang();
  const dialog = useDialog();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(null);

  async function run(action) {
    setBusy(true);
    setNote(null);
    try {
      await action();
      onChanged();
    } catch (e) {
      setNote(e.message);
    } finally {
      setBusy(false);
    }
  }

  function add(e) {
    e.preventDefault();
    const n = name.trim();
    if (!n) return;
    run(async () => {
      await api.post("/api/library/topics", { name: n });
      setName("");
    });
  }

  async function rename(tp) {
    const n = await dialog.eingabe({
      titel: t("Thema umbenennen", "Rename topic"),
      text: t("Der Titel erscheint als Filter für die Schüler:innen.", "The title appears as a filter for students."),
      wert: tp.name,
      bestaetigen: t("Speichern", "Save"),
    });
    if (!n || n === tp.name) return;
    run(() => api.patch(`/api/library/topics/${tp.id}`, { name: n }));
  }

  async function remove(tp) {
    const ja = await dialog.bestaetigen({
      titel: t(`Thema «${tp.name}» löschen?`, `Delete topic “${tp.name}”?`),
      text: t("Geht nur, wenn keine Aufgabe mehr darin liegt.", "Only possible if no task is left in it."),
      bestaetigen: t("Löschen", "Delete"),
      gefahr: true,
    });
    if (!ja) return;
    run(() => api.del(`/api/library/topics/${tp.id}`));
  }

  return (
    <div style={{ background: "#fff", border: "1px solid #e0e2fb", borderRadius: 14, padding: 18, marginTop: 14 }}>
      <div style={{ fontSize: 14, fontWeight: 800, marginBottom: 4 }}>{t("Themen verwalten", "Manage topics")}</div>
      <div style={{ fontSize: 12, color: "#9aa0ab", marginBottom: 12 }}>
        {t("Deine eigenen Themen-Titel – sie erscheinen als Filter für die Schüler:innen und als Auswahl beim Eintragen.", "Your own topic titles – they appear as filters for students and as options when adding tasks.")}
      </div>
      <form onSubmit={add} style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("z.B. Prozentrechnen, Pythagoras, Terme umformen …", "e.g. percentages, Pythagoras, transforming terms …")} style={{ flex: 1, border: "1px solid #d2d4dd", borderRadius: 10, padding: "9px 12px", fontSize: 13, outline: "none" }} />
        <button type="submit" disabled={busy || !name.trim()} className="btn-primary" style={{ borderRadius: 10, padding: "9px 16px", fontSize: 13, opacity: busy || !name.trim() ? 0.6 : 1 }}>
          {t("+ Hinzufügen", "+ Add")}
        </button>
      </form>
      {note && <div style={noteStyle(true)}>{note}</div>}
      {topics.length === 0 ? (
        <div style={{ fontSize: 13, color: "#9aa0ab" }}>{t("Noch keine Themen angelegt.", "No topics created yet.")}</div>
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {topics.map((tp) => (
            <span key={tp.id} style={{ display: "inline-flex", alignItems: "center", gap: 7, border: "1px solid #e7e8ee", borderRadius: 999, padding: "6px 6px 6px 12px", fontSize: 12, fontWeight: 600, background: "#fbfbfd" }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: colorFor(tp.name) }} />
              {tp.name}
              <span style={{ color: "#b6bcc6", fontWeight: 400 }}>({tp.doc_count})</span>
              <button type="button" onClick={() => rename(tp)} title={t("Umbenennen", "Rename")} style={{ border: "none", background: "#f1f2f6", borderRadius: 999, width: 22, height: 22, cursor: "pointer", fontSize: 11 }}>✎</button>
              <button type="button" onClick={() => remove(tp)} title={t("Löschen", "Delete")} style={{ border: "none", background: "#fdecec", color: "#c0392b", borderRadius: 999, width: 22, height: 22, cursor: "pointer", fontSize: 11 }}>✕</button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
