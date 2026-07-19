import { useCallback, useEffect, useRef, useState } from "react";
import { api, getToken } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";
import { useLang, GRADE_KEYS, gradeLabel, gradeShort } from "../lib/i18n.jsx";

const BASE = import.meta.env.VITE_API_BASE || "";

// Stabile Farbe pro Themen-Name (Themen sind frei benennbar)
const PALETTE = ["#6366f1", "#e0993a", "#1a7f3c", "#c0392b", "#0e7490", "#7c3aed", "#b45309"];
function colorFor(name) {
  let h = 0;
  for (const c of name || "") h = (h * 31 + c.charCodeAt(0)) % 9973;
  return PALETTE[h % PALETTE.length];
}

function fmtSize(bytes) {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function ChipRow({ label, options, value, onChange }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
      <span style={{ fontSize: 11, fontWeight: 700, color: "#9aa0ab", width: 88, flex: "0 0 88px" }}>{label}</span>
      {options.map(([val, lbl]) => (
        <button
          key={val}
          onClick={() => onChange(val)}
          style={{
            fontSize: 12, fontWeight: 600, borderRadius: 999, padding: "5px 12px", cursor: "pointer",
            background: value === val ? "#eef0fe" : "#fff",
            color: value === val ? "#4f46e5" : "#6b7280",
            border: `1px solid ${value === val ? "#c9ccf6" : "#e7e8ee"}`,
          }}
        >
          {lbl}
        </button>
      ))}
    </div>
  );
}

export default function Bibliothek() {
  const { user } = useAuth();
  const { t, lang } = useLang();
  const [q, setQ] = useState("");
  const [activeQ, setActiveQ] = useState(""); // zuletzt wirklich gesuchter Begriff
  const [grade, setGrade] = useState("");
  const [category, setCategory] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [docs, setDocs] = useState(null); // null = lädt
  const [topics, setTopics] = useState([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);
  const [adminOpen, setAdminOpen] = useState(false);
  const reqToken = useRef(0);

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

  useEffect(() => {
    loadTopics();
  }, [loadTopics]);

  const load = useCallback(async (searchTerm) => {
    const my = ++reqToken.current;
    setError(null);
    if (searchTerm) setSearching(true);
    try {
      const params = new URLSearchParams();
      if (searchTerm) params.set("q", searchTerm);
      if (grade) params.set("grade", grade);
      if (category) params.set("category", category);
      if (difficulty) params.set("difficulty", difficulty);
      const res = await api.get(`/api/library${params.size ? `?${params}` : ""}`);
      if (my !== reqToken.current) return;
      setDocs(res);
    } catch (e) {
      if (my !== reqToken.current) return;
      setError(e.message);
      setDocs([]);
    } finally {
      if (my === reqToken.current) setSearching(false);
    }
  }, [grade, category, difficulty]);

  // Chips wirken sofort (reine SQL-Filter); Freitext nur auf Enter/Suchen
  useEffect(() => {
    load(activeQ);
  }, [load, activeQ]);

  function submitSearch(e) {
    e?.preventDefault();
    setActiveQ(q.trim());
    if (q.trim() === activeQ) load(q.trim()); // gleiche Anfrage nochmal ausführen
  }

  async function openDoc(doc) {
    try {
      const res = await fetch(`${BASE}/api/library/${doc.id}/file`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!res.ok) throw new Error(t("Dokument konnte nicht geladen werden.", "The document could not be loaded."));
      const url = URL.createObjectURL(await res.blob());
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      setError(e.message);
    }
  }

  async function removeDoc(doc) {
    if (!window.confirm(t(`«${doc.title}» wirklich löschen?`, `Really delete "${doc.title}"?`))) return;
    try {
      await api.del(`/api/library/${doc.id}`);
      load(activeQ);
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div style={{ height: "100%", overflowY: "auto", background: "#f6f7fb" }}>
      <div style={{ maxWidth: 860, margin: "0 auto", padding: "26px 24px 60px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 4 }}>
          <div>
            <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-.02em" }}>{t("📚 Aufgaben-Bibliothek", "📚 Task Library")}</div>
            <div style={{ fontSize: 13, color: "#6b7280" }}>{t("Arbeitsblätter zum Üben – such nach Thema oder filtere nach deiner Klasse.", "Worksheets for practice – search by topic or filter by your level.")}</div>
          </div>
          {user?.is_admin && (
            <button onClick={() => setAdminOpen((v) => !v)} className="btn-ghost" style={{ fontSize: 12, padding: "9px 14px", borderRadius: 999, whiteSpace: "nowrap" }}>
              {adminOpen ? t("✕ Verwalten schliessen", "✕ Close manage") : t("⚙ Verwalten", "⚙ Manage")}
            </button>
          )}
        </div>

        {user?.is_admin && adminOpen && (
          <>
            <TopicManager topics={topics} onChanged={() => { loadTopics(); load(activeQ); }} />
            <AdminUpload topics={topics} onDone={() => { loadTopics(); load(activeQ); }} />
          </>
        )}

        <form onSubmit={submitSearch} style={{ display: "flex", gap: 8, margin: "18px 0 12px" }}>
          <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 8, background: "#fff", border: "1px solid #d2d4dd", borderRadius: 12, padding: "10px 14px" }}>
            <span style={{ color: "#b6bcc6" }}>🔎</span>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={t("z.B. Gleichungen mit Brüchen, Prozentrechnen, Satz des Pythagoras …", "e.g. equations with fractions, percentages, Pythagorean theorem …")}
              style={{ flex: 1, border: "none", outline: "none", fontSize: 13, background: "transparent" }}
            />
          </div>
          <button type="submit" className="btn-primary" style={{ borderRadius: 12, padding: "10px 18px", fontSize: 13 }}>
            {searching ? t("KI sucht …", "AI is searching …") : t("Suchen", "Search")}
          </button>
        </form>

        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 20 }}>
          <ChipRow label={t("THEMA", "TOPIC")} options={[["", t("Alle", "All")], ...topics.map((tp) => [tp.name, tp.name])]} value={category} onChange={setCategory} />
          <ChipRow label={t("STUFE", "LEVEL")} options={GRADES} value={grade} onChange={setGrade} />
          <ChipRow label={t("SCHWIERIGKEIT", "DIFFICULTY")} options={DIFFICULTIES} value={difficulty} onChange={setDifficulty} />
        </div>

        {error && (
          <div style={{ fontSize: 13, background: "#fdecec", color: "#c0392b", border: "1px solid #f5cccc", borderRadius: 10, padding: "10px 14px", marginBottom: 14 }}>{error}</div>
        )}

        {docs === null ? (
          <div style={{ color: "#9aa0ab", fontSize: 14, textAlign: "center", padding: 40 }}>{t("lädt …", "loading …")}</div>
        ) : docs.length === 0 ? (
          <div style={{ textAlign: "center", padding: "48px 20px", color: "#6b7280" }}>
            <div style={{ fontSize: 30, marginBottom: 10 }}>🗂️</div>
            <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>
              {activeQ || grade || category || difficulty ? t("Keine Dokumente gefunden", "No documents found") : t("Die Bibliothek ist noch leer.", "The library is still empty.")}
            </div>
            {(activeQ || grade || category || difficulty) && (
              <div style={{ fontSize: 13 }}>{t("Probier andere Suchbegriffe oder Filter.", "Try other search terms or filters.")}</div>
            )}
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {docs.map((d) => (
              <div key={d.id} style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 14, padding: "16px 18px", display: "flex", gap: 14, alignItems: "flex-start" }}>
                <div style={{ flex: "0 0 42px", height: 42, borderRadius: 10, background: "#eef0fe", display: "grid", placeItems: "center", fontSize: 19 }}>
                  {d.mime_type === "application/pdf" ? "📄" : "🖼️"}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 3 }}>{d.title}</div>
                  <div style={{ fontSize: 13, color: "#6b7280", lineHeight: 1.5, marginBottom: 8 }}>{d.description}</div>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                    <span style={{ fontSize: 11, fontWeight: 700, borderRadius: 999, padding: "3px 10px", background: `${colorFor(d.category)}18`, color: colorFor(d.category) }}>
                      {d.category}
                    </span>
                    {d.grade_levels.map((g) => (
                      <span key={g} style={{ fontSize: 11, fontWeight: 600, borderRadius: 999, padding: "3px 10px", background: "#f1f2f6", color: "#6b7280" }}>{gradeShort(g, lang)}</span>
                    ))}
                    <span style={{ fontSize: 11, fontWeight: 600, borderRadius: 999, padding: "3px 10px", background: "#f1f2f6", color: "#6b7280" }}>{diffLabel[d.difficulty] || d.difficulty}</span>
                    <span style={{ fontSize: 11, color: "#b6bcc6" }}>{fmtSize(d.size_bytes)}</span>
                  </div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <button onClick={() => openDoc(d)} className="btn-primary" style={{ fontSize: 12, borderRadius: 10, padding: "9px 16px", whiteSpace: "nowrap" }}>
                    {t("Öffnen", "Open")}
                  </button>
                  {user?.is_admin && (
                    <button onClick={() => removeDoc(d)} style={{ fontSize: 11, border: "1px solid #f5cccc", background: "#fff", color: "#c0392b", borderRadius: 10, padding: "7px 12px", cursor: "pointer" }}>
                      {t("Löschen", "Delete")}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function AdminUpload({ topics, onDone }) {
  const { t, lang } = useLang();
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [category, setCategory] = useState("");
  const [grades, setGrades] = useState([]);
  const [difficulty, setDifficulty] = useState("mittel");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(null); // {type, text}

  function toggleGrade(g) {
    setGrades((prev) => (prev.includes(g) ? prev.filter((x) => x !== g) : [...prev, g]));
  }

  async function submit(e) {
    e.preventDefault();
    if (!file) return setNote({ type: "error", text: t("Bitte eine Datei wählen (PDF oder Bild).", "Please choose a file (PDF or image).") });
    if (file.size > 4 * 1024 * 1024) return setNote({ type: "error", text: t("Die Datei ist zu gross (max. 4 MB).", "The file is too large (max. 4 MB).") });
    if (!title.trim()) return setNote({ type: "error", text: t("Bitte einen Titel angeben.", "Please enter a title.") });
    if (!desc.trim()) return setNote({ type: "error", text: t("Bitte das Thema beschreiben – die Beschreibung ist die Basis der KI-Suche.", "Please describe the topic – the description is the basis of the AI search.") });
    if (grades.length === 0) return setNote({ type: "error", text: t("Bitte mindestens eine Klassenstufe wählen.", "Please select at least one level.") });
    if (!category) return setNote({ type: "error", text: t("Bitte ein Thema wählen – oder oben unter «Themen» eines anlegen.", "Please select a topic – or create one above under \"Topics\".") });
    setBusy(true);
    setNote(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("title", title.trim());
      fd.append("description", desc.trim());
      fd.append("category", category);
      fd.append("grade_levels", grades.join(","));
      fd.append("difficulty", difficulty);
      await api.upload("/api/library", fd);
      setNote({ type: "ok", text: t("Dokument hochgeladen. ✓", "Document uploaded. ✓") });
      setFile(null);
      setTitle("");
      setDesc("");
      setGrades([]);
      onDone();
    } catch (e2) {
      setNote({ type: "error", text: e2.message });
    } finally {
      setBusy(false);
    }
  }

  const label = { fontSize: 12, fontWeight: 600, color: "#6b7280", display: "block", marginBottom: 5 };
  const input = { width: "100%", border: "1px solid #d2d4dd", borderRadius: 10, padding: "9px 12px", fontSize: 13, outline: "none", background: "#fff" };

  return (
    <form onSubmit={submit} style={{ background: "#fff", border: "1px solid #e0e2fb", borderRadius: 14, padding: 18, marginTop: 14, display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ fontSize: 14, fontWeight: 800 }}>{t("Neues Dokument hochladen", "Upload new document")}</div>
      <div>
        <label style={label}>{t("Datei (PDF oder Bild, max. 4 MB)", "File (PDF or image, max. 4 MB)")}</label>
        <input type="file" accept=".pdf,image/png,image/jpeg,image/webp" onChange={(e) => setFile(e.target.files?.[0] || null)} style={{ fontSize: 13 }} />
      </div>
      <div>
        <label style={label}>{t("Titel", "Title")}</label>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder={t("z.B. Lineare Gleichungen – Übungsblatt 1", "e.g. Linear equations – practice sheet 1")} style={input} />
      </div>
      <div>
        <label style={label}>{t("Thema-Beschreibung (je genauer, desto besser findet die Suche das Dokument)", "Topic description (the more precise, the better the search finds the document)")}</label>
        <textarea value={desc} onChange={(e) => setDesc(e.target.value)} rows={3} placeholder={t("z.B. 12 Übungen zu linearen Gleichungen mit einer Unbekannten, inkl. Brüchen und Klammern. Mit Lösungsteil.", "e.g. 12 exercises on linear equations with one unknown, incl. fractions and brackets. With solutions.")} style={{ ...input, resize: "vertical" }} />
      </div>
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
        <div>
          <label style={label}>{t("Thema", "Topic")}</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)} style={input}>
            <option value="">{t("– wählen –", "– select –")}</option>
            {topics.map((tp) => (
              <option key={tp.id} value={tp.name}>{tp.name}</option>
            ))}
          </select>
          {topics.length === 0 && (
            <div style={{ fontSize: 11, color: "#c0392b", marginTop: 4 }}>{t("Noch keine Themen – leg zuerst oben eines an.", "No topics yet – create one above first.")}</div>
          )}
        </div>
        <div>
          <label style={label}>{t("Klassenstufen", "Levels")}</label>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {GRADE_KEYS.map((g) => (
              <button type="button" key={g} onClick={() => toggleGrade(g)} style={{ fontSize: 12, fontWeight: 600, borderRadius: 999, padding: "7px 12px", cursor: "pointer", background: grades.includes(g) ? "#eef0fe" : "#fff", color: grades.includes(g) ? "#4f46e5" : "#6b7280", border: `1px solid ${grades.includes(g) ? "#c9ccf6" : "#e7e8ee"}` }}>
                {gradeLabel(g, lang)}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label style={label}>{t("Schwierigkeit", "Difficulty")}</label>
          <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} style={input}>
            <option value="leicht">{t("Leicht", "Easy")}</option>
            <option value="mittel">{t("Mittel", "Medium")}</option>
            <option value="schwer">{t("Schwer", "Hard")}</option>
          </select>
        </div>
      </div>
      {note && (
        <div style={{ fontSize: 13, borderRadius: 10, padding: "9px 12px", background: note.type === "error" ? "#fdecec" : "#e8f6ec", color: note.type === "error" ? "#c0392b" : "#1a7f3c", border: `1px solid ${note.type === "error" ? "#f5cccc" : "#cde7d6"}` }}>
          {note.text}
        </div>
      )}
      <button type="submit" disabled={busy} className="btn-primary" style={{ alignSelf: "flex-start", borderRadius: 10, padding: "10px 20px", fontSize: 13, opacity: busy ? 0.6 : 1 }}>
        {busy ? t("lädt hoch …", "uploading …") : t("Hochladen", "Upload")}
      </button>
    </form>
  );
}

function TopicManager({ topics, onChanged }) {
  const { t, lang } = useLang();
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

  function rename(tp) {
    const n = window.prompt(t("Neuer Titel für das Thema:", "New title for the topic:"), tp.name);
    if (!n || !n.trim() || n.trim() === tp.name) return;
    run(() => api.patch(`/api/library/topics/${tp.id}`, { name: n.trim() }));
  }

  function remove(tp) {
    if (!window.confirm(t(`Thema «${tp.name}» löschen?`, `Delete topic "${tp.name}"?`))) return;
    run(() => api.del(`/api/library/topics/${tp.id}`));
  }

  return (
    <div style={{ background: "#fff", border: "1px solid #e0e2fb", borderRadius: 14, padding: 18, marginTop: 14 }}>
      <div style={{ fontSize: 14, fontWeight: 800, marginBottom: 4 }}>{t("Themen verwalten", "Manage topics")}</div>
      <div style={{ fontSize: 12, color: "#9aa0ab", marginBottom: 12 }}>
        {t("Deine eigenen Themen-Titel – sie erscheinen als Filter für die Schüler:innen und als Auswahl beim Hochladen.", "Your own topic titles – they appear as filters for students and as options when uploading.")}
      </div>
      <form onSubmit={add} style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t("z.B. Prozentrechnen, Pythagoras, Terme umformen …", "e.g. percentages, Pythagoras, transforming terms …")}
          style={{ flex: 1, border: "1px solid #d2d4dd", borderRadius: 10, padding: "9px 12px", fontSize: 13, outline: "none" }}
        />
        <button type="submit" disabled={busy || !name.trim()} className="btn-primary" style={{ borderRadius: 10, padding: "9px 16px", fontSize: 13, opacity: busy || !name.trim() ? 0.6 : 1 }}>
          {t("+ Hinzufügen", "+ Add")}
        </button>
      </form>
      {note && (
        <div style={{ fontSize: 13, background: "#fdecec", color: "#c0392b", border: "1px solid #f5cccc", borderRadius: 10, padding: "8px 12px", marginBottom: 10 }}>{note}</div>
      )}
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
