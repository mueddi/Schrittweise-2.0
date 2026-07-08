import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";
import { useShell } from "../components/AppShell.jsx";
import { useAuth } from "../lib/auth.jsx";

const FILTERS = [
  { key: "alle", label: "Alle" },
  { key: "algebra", label: "Algebra" },
  { key: "geometrie", label: "Geometrie" },
  { key: "zahlen", label: "Zahlen" },
];
const CAT_COLORS = {
  algebra: ["#eef0fe", "#4f46e5"],
  geometrie: ["#fdf0e6", "#c26a1f"],
  zahlen: ["#e8f6ec", "#1a7f3c"],
  andere: ["#f1f2f6", "#6b7280"],
};
const LABEL_COLOR = { Sitzt: "#1a7f3c", "Wird besser": "#4f46e5", "Noch üben": "#c0392b", Neu: "#6b7280" };

function TopicGrid() {
  const shell = useShell();
  const { user } = useAuth();
  const nav = useNavigate();
  const [filter, setFilter] = useState("alle");
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [cat, setCat] = useState("algebra");

  const topics = (shell.topics || []).filter((t) => filter === "alle" || t.category === filter);

  async function createTopic() {
    if (!name.trim()) return;
    await api.post("/api/topics", { name: name.trim(), category: cat });
    setName("");
    setAdding(false);
    shell.reloadTopics?.();
  }

  return (
    <div style={{ height: "100%", overflowY: "auto", background: "#fbfbfd" }}>
      <div style={{ padding: "24px 28px 8px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-.02em", marginBottom: 4 }}>Themen</div>
            <div style={{ fontSize: 14, color: "#6b7280", marginBottom: 18 }}>{user?.grade_level || "Oberstufe"} · Lehrplan 21</div>
          </div>
          <button onClick={() => setAdding((v) => !v)} className="btn-primary" style={{ padding: "10px 16px", borderRadius: 11, fontSize: 13, border: "none" }}>+ Neues Thema</button>
        </div>
        {adding && (
          <div className="popin" style={{ display: "flex", gap: 8, marginBottom: 16, background: "#fff", border: "1px solid #e7e8ee", borderRadius: 14, padding: 12 }}>
            <input autoFocus value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && createTopic()} placeholder="Themen-Name, z.B. Bruchrechnen" style={{ flex: 1, border: "1px solid #d2d4dd", borderRadius: 10, padding: "9px 12px", fontSize: 14, outline: "none" }} />
            <select value={cat} onChange={(e) => setCat(e.target.value)} style={{ border: "1px solid #d2d4dd", borderRadius: 10, padding: "9px 12px", fontSize: 14, background: "#fff" }}>
              <option value="algebra">Algebra</option>
              <option value="geometrie">Geometrie</option>
              <option value="zahlen">Zahlen</option>
              <option value="andere">Andere</option>
            </select>
            <button onClick={createTopic} className="btn-primary" style={{ padding: "9px 16px", borderRadius: 10, fontSize: 13, border: "none" }}>Anlegen</button>
          </div>
        )}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {FILTERS.map((f) => (
            <span key={f.key} onClick={() => setFilter(f.key)} style={{ cursor: "pointer", fontSize: 13, fontWeight: 600, color: filter === f.key ? "#4f46e5" : "#6b7280", background: filter === f.key ? "#eef0fe" : "#fff", border: filter === f.key ? "none" : "1px solid #e7e8ee", borderRadius: 999, padding: "7px 14px" }}>{f.label}</span>
          ))}
        </div>
      </div>
      <div style={{ padding: "14px 28px 28px", display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 16 }} className="themen-grid">
        {topics.length === 0 && (
          <div style={{ gridColumn: "1 / -1", background: "#fff", border: "1px dashed #d2d4dd", borderRadius: 16, padding: 30, textAlign: "center", color: "#6b7280" }}>
            <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 6, color: "#1a1c22" }}>Noch keine Themen{filter !== "alle" ? " in dieser Kategorie" : ""}</div>
            <div style={{ fontSize: 13 }}>Themen sind deine eigenen Container – leg oben eins an und ordne Aufgaben zu.</div>
          </div>
        )}
        {topics.map((k) => {
          const [bg, fg] = CAT_COLORS[k.category] || CAT_COLORS.andere;
          return (
            <div key={k.id} onClick={() => nav(`/app/themen/${k.id}`)} style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 16, padding: 18, boxShadow: "0 1px 2px rgba(40,40,90,.04)", cursor: "pointer" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
                <span style={{ width: 36, height: 36, borderRadius: 11, fontWeight: 800, fontSize: 15, display: "grid", placeItems: "center", background: bg, color: fg }}>{k.name.charAt(0).toUpperCase()}</span>
                <span style={{ fontSize: 11, fontWeight: 700, borderRadius: 999, padding: "3px 10px", background: bg, color: LABEL_COLOR[k.progress_label] || fg }}>{k.progress_label}</span>
              </div>
              <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>{k.name}</div>
              <div style={{ fontSize: 12, color: "#9aa0ab", marginBottom: 12 }}>{k.solved_count}/{k.exercise_count} gelöst</div>
              <div style={{ height: 6, borderRadius: 999, background: "#eef0f3", overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${k.progress_pct}%`, background: k.progress_pct >= 90 ? "#1a7f3c" : "#6366f1" }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TopicDetail({ topicId }) {
  const shell = useShell();
  const nav = useNavigate();
  const topic = (shell.topics || []).find((t) => String(t.id) === String(topicId));
  const [exercises, setExercises] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setExercises(await api.get(`/api/topics/${topicId}/exercises`));
    } catch {
      setExercises([]);
    }
  }, [topicId]);
  useEffect(() => { load(); }, [load]);

  async function open(ex) {
    if (busy) return;
    setBusy(true);
    try {
      if (ex.latest_attempt_id) {
        nav(`/app/lernen/${ex.latest_attempt_id}`);
      } else {
        const st = await api.post(`/api/exercises/${ex.id}/attempts`, {});
        nav(`/app/lernen/${st.attempt.id}`);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ height: "100%", overflowY: "auto", background: "#fbfbfd" }}>
      <div style={{ padding: "24px 28px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
          <span onClick={() => nav("/app/themen")} style={{ fontSize: 13, fontWeight: 600, color: "#4f46e5", cursor: "pointer" }}>← Themen</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
          <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-.02em" }}>{topic?.name || "Thema"}</div>
          <button onClick={() => shell.openNewTask(Number(topicId))} className="btn-primary" style={{ padding: "10px 16px", borderRadius: 11, fontSize: 13, border: "none" }}>+ Neue Aufgabe</button>
        </div>
        {exercises.length === 0 && (
          <div style={{ background: "#fff", border: "1px dashed #d2d4dd", borderRadius: 16, padding: 30, textAlign: "center", color: "#6b7280" }}>
            <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 6, color: "#1a1c22" }}>Noch keine Aufgaben</div>
            <div style={{ fontSize: 13 }}>Leg mit «+ Neue Aufgabe» los – tippen oder fotografieren.</div>
          </div>
        )}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {exercises.map((ex) => (
            <div key={ex.id} onClick={() => open(ex)} style={{ display: "flex", alignItems: "center", gap: 14, background: "#fff", border: "1px solid #e7e8ee", borderRadius: 14, padding: "14px 16px", cursor: "pointer" }}>
              <span style={{ width: 34, height: 34, borderRadius: 10, display: "grid", placeItems: "center", background: ex.solved ? "#e8f6ec" : "#eef0fe", color: ex.solved ? "#1a7f3c" : "#4f46e5", fontWeight: 700 }}>{ex.solved ? "✓" : "∑"}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{ex.text}</div>
                <div style={{ fontSize: 12, color: "#9aa0ab" }}>{ex.solved ? "gelöst" : ex.latest_attempt_id ? "weiter üben" : "noch nicht gestartet"}</div>
              </div>
              <span style={{ color: "#b6bcc6", fontSize: 18 }}>›</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function Themen() {
  const { topicId } = useParams();
  return topicId ? <TopicDetail topicId={topicId} /> : <TopicGrid />;
}
