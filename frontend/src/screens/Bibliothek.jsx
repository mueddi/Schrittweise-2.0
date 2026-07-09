import { useCallback, useEffect, useRef, useState } from "react";
import { api, getToken } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";

const BASE = import.meta.env.VITE_API_BASE || "";

const CATEGORIES = [
  ["", "Alle"],
  ["algebra", "Algebra"],
  ["geometrie", "Geometrie"],
  ["zahlen", "Zahlen"],
  ["andere", "Andere"],
];
const GRADES = [["", "Alle"], ["1. Oberstufe", "1. OS"], ["2. Oberstufe", "2. OS"], ["3. Oberstufe", "3. OS"]];
const DIFFICULTIES = [["", "Alle"], ["leicht", "Leicht"], ["mittel", "Mittel"], ["schwer", "Schwer"]];
const CAT_COLOR = { algebra: "#6366f1", geometrie: "#e0993a", zahlen: "#1a7f3c", andere: "#9aa0ab" };

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
  const [q, setQ] = useState("");
  const [activeQ, setActiveQ] = useState(""); // zuletzt wirklich gesuchter Begriff
  const [grade, setGrade] = useState("");
  const [category, setCategory] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [docs, setDocs] = useState(null); // null = lädt
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);
  const [adminOpen, setAdminOpen] = useState(false);
  const reqToken = useRef(0);

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
      if (!res.ok) throw new Error("Dokument konnte nicht geladen werden.");
      const url = URL.createObjectURL(await res.blob());
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      setError(e.message);
    }
  }

  async function removeDoc(doc) {
    if (!window.confirm(`«${doc.title}» wirklich löschen?`)) return;
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
            <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-.02em" }}>📚 Aufgaben-Bibliothek</div>
            <div style={{ fontSize: 13, color: "#6b7280" }}>Arbeitsblätter zum Üben – such nach Thema oder filtere nach deiner Klasse.</div>
          </div>
          {user?.is_admin && (
            <button onClick={() => setAdminOpen((v) => !v)} className="btn-ghost" style={{ fontSize: 12, padding: "9px 14px", borderRadius: 999, whiteSpace: "nowrap" }}>
              {adminOpen ? "✕ Verwalten schliessen" : "⚙ Verwalten"}
            </button>
          )}
        </div>

        {user?.is_admin && adminOpen && <AdminUpload onDone={() => load(activeQ)} />}

        <form onSubmit={submitSearch} style={{ display: "flex", gap: 8, margin: "18px 0 12px" }}>
          <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 8, background: "#fff", border: "1px solid #d2d4dd", borderRadius: 12, padding: "10px 14px" }}>
            <span style={{ color: "#b6bcc6" }}>🔎</span>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="z.B. Gleichungen mit Brüchen, Prozentrechnen, Satz des Pythagoras …"
              style={{ flex: 1, border: "none", outline: "none", fontSize: 13, background: "transparent" }}
            />
          </div>
          <button type="submit" className="btn-primary" style={{ borderRadius: 12, padding: "10px 18px", fontSize: 13 }}>
            {searching ? "KI sucht …" : "Suchen"}
          </button>
        </form>

        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 20 }}>
          <ChipRow label="THEMA" options={CATEGORIES} value={category} onChange={setCategory} />
          <ChipRow label="KLASSE" options={GRADES} value={grade} onChange={setGrade} />
          <ChipRow label="SCHWIERIGKEIT" options={DIFFICULTIES} value={difficulty} onChange={setDifficulty} />
        </div>

        {error && (
          <div style={{ fontSize: 13, background: "#fdecec", color: "#c0392b", border: "1px solid #f5cccc", borderRadius: 10, padding: "10px 14px", marginBottom: 14 }}>{error}</div>
        )}

        {docs === null ? (
          <div style={{ color: "#9aa0ab", fontSize: 14, textAlign: "center", padding: 40 }}>lädt …</div>
        ) : docs.length === 0 ? (
          <div style={{ textAlign: "center", padding: "48px 20px", color: "#6b7280" }}>
            <div style={{ fontSize: 30, marginBottom: 10 }}>🗂️</div>
            <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>
              {activeQ || grade || category || difficulty ? "Keine Dokumente gefunden" : "Die Bibliothek ist noch leer."}
            </div>
            {(activeQ || grade || category || difficulty) && (
              <div style={{ fontSize: 13 }}>Probier andere Suchbegriffe oder Filter.</div>
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
                    <span style={{ fontSize: 11, fontWeight: 700, borderRadius: 999, padding: "3px 10px", background: `${CAT_COLOR[d.category] || "#9aa0ab"}18`, color: CAT_COLOR[d.category] || "#9aa0ab" }}>
                      {d.category}
                    </span>
                    {d.grade_levels.map((g) => (
                      <span key={g} style={{ fontSize: 11, fontWeight: 600, borderRadius: 999, padding: "3px 10px", background: "#f1f2f6", color: "#6b7280" }}>{g}</span>
                    ))}
                    <span style={{ fontSize: 11, fontWeight: 600, borderRadius: 999, padding: "3px 10px", background: "#f1f2f6", color: "#6b7280" }}>{d.difficulty}</span>
                    <span style={{ fontSize: 11, color: "#b6bcc6" }}>{fmtSize(d.size_bytes)}</span>
                  </div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <button onClick={() => openDoc(d)} className="btn-primary" style={{ fontSize: 12, borderRadius: 10, padding: "9px 16px", whiteSpace: "nowrap" }}>
                    Öffnen
                  </button>
                  {user?.is_admin && (
                    <button onClick={() => removeDoc(d)} style={{ fontSize: 11, border: "1px solid #f5cccc", background: "#fff", color: "#c0392b", borderRadius: 10, padding: "7px 12px", cursor: "pointer" }}>
                      Löschen
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

function AdminUpload({ onDone }) {
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [category, setCategory] = useState("andere");
  const [grades, setGrades] = useState([]);
  const [difficulty, setDifficulty] = useState("mittel");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(null); // {type, text}

  function toggleGrade(g) {
    setGrades((prev) => (prev.includes(g) ? prev.filter((x) => x !== g) : [...prev, g]));
  }

  async function submit(e) {
    e.preventDefault();
    if (!file) return setNote({ type: "error", text: "Bitte eine Datei wählen (PDF oder Bild)." });
    if (file.size > 4 * 1024 * 1024) return setNote({ type: "error", text: "Die Datei ist zu gross (max. 4 MB)." });
    if (!title.trim()) return setNote({ type: "error", text: "Bitte einen Titel angeben." });
    if (!desc.trim()) return setNote({ type: "error", text: "Bitte das Thema beschreiben – die Beschreibung ist die Basis der KI-Suche." });
    if (grades.length === 0) return setNote({ type: "error", text: "Bitte mindestens eine Klassenstufe wählen." });
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
      setNote({ type: "ok", text: "Dokument hochgeladen. ✓" });
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
      <div style={{ fontSize: 14, fontWeight: 800 }}>Neues Dokument hochladen</div>
      <div>
        <label style={label}>Datei (PDF oder Bild, max. 4 MB)</label>
        <input type="file" accept=".pdf,image/png,image/jpeg,image/webp" onChange={(e) => setFile(e.target.files?.[0] || null)} style={{ fontSize: 13 }} />
      </div>
      <div>
        <label style={label}>Titel</label>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="z.B. Lineare Gleichungen – Übungsblatt 1" style={input} />
      </div>
      <div>
        <label style={label}>Thema-Beschreibung (je genauer, desto besser findet die Suche das Dokument)</label>
        <textarea value={desc} onChange={(e) => setDesc(e.target.value)} rows={3} placeholder="z.B. 12 Übungen zu linearen Gleichungen mit einer Unbekannten, inkl. Brüchen und Klammern. Mit Lösungsteil." style={{ ...input, resize: "vertical" }} />
      </div>
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
        <div>
          <label style={label}>Thema</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)} style={input}>
            <option value="algebra">Algebra</option>
            <option value="geometrie">Geometrie</option>
            <option value="zahlen">Zahlen</option>
            <option value="andere">Andere</option>
          </select>
        </div>
        <div>
          <label style={label}>Klassenstufen</label>
          <div style={{ display: "flex", gap: 6 }}>
            {["1. Oberstufe", "2. Oberstufe", "3. Oberstufe"].map((g) => (
              <button type="button" key={g} onClick={() => toggleGrade(g)} style={{ fontSize: 12, fontWeight: 600, borderRadius: 999, padding: "7px 12px", cursor: "pointer", background: grades.includes(g) ? "#eef0fe" : "#fff", color: grades.includes(g) ? "#4f46e5" : "#6b7280", border: `1px solid ${grades.includes(g) ? "#c9ccf6" : "#e7e8ee"}` }}>
                {g}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label style={label}>Schwierigkeit</label>
          <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} style={input}>
            <option value="leicht">Leicht</option>
            <option value="mittel">Mittel</option>
            <option value="schwer">Schwer</option>
          </select>
        </div>
      </div>
      {note && (
        <div style={{ fontSize: 13, borderRadius: 10, padding: "9px 12px", background: note.type === "error" ? "#fdecec" : "#e8f6ec", color: note.type === "error" ? "#c0392b" : "#1a7f3c", border: `1px solid ${note.type === "error" ? "#f5cccc" : "#cde7d6"}` }}>
          {note.text}
        </div>
      )}
      <button type="submit" disabled={busy} className="btn-primary" style={{ alignSelf: "flex-start", borderRadius: 10, padding: "10px 20px", fontSize: 13, opacity: busy ? 0.6 : 1 }}>
        {busy ? "lädt hoch …" : "Hochladen"}
      </button>
    </form>
  );
}
