import { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, getToken } from "../lib/api.js";
import { useShell } from "../components/AppShell.jsx";
import MathText from "../lib/MathText.jsx";

const BASE = import.meta.env.VITE_API_BASE || "";

const STUFEN_LABEL = {
  1: "Stufe 1: Aktivierende Frage",
  2: "Stufe 2: Kleiner Tipp",
  3: "Stufe 3: Teilschritt vorgemacht",
  4: "Stufe 4: Volle Lösung",
};

function Ladder({ level, solved }) {
  const accent = solved ? "#1a7f3c" : "#4f46e5";
  const bg = solved ? "#e8f6ec" : "#eef0fe";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, background: bg, borderRadius: 999, padding: "6px 14px", transition: "background .3s" }}>
      <span style={{ fontSize: 11, fontWeight: 700, color: accent }}>HINWEIS-LEITER</span>
      {[1, 2, 3, 4].map((i) => (
        <span
          key={i}
          title={STUFEN_LABEL[i]}
          className={`ladder-dot ${i <= level ? "filled" : ""}`}
          style={{
            width: 9, height: 9, borderRadius: "50%", display: "inline-block", cursor: "help",
            background: i <= level ? accent : "#fff",
            border: i <= level ? "none" : `1.5px solid ${solved ? "#bfe3cb" : "#c9ccf6"}`,
          }}
        />
      ))}
      <span style={{ fontSize: 11, fontWeight: 600, color: accent }}>
        {solved ? "Gelöst 🎉" : `Stufe ${Math.max(level, 0)}/4`}
      </span>
    </div>
  );
}

// Visuelles Feedback zur SymPy-Prüfung unter der Schüler-Bubble (nie die Lösung)
const VERIFY_CHIP = {
  correct: { label: "✓ stimmt!", bg: "#e8f6ec", fg: "#1a7f3c" },
  partial: { label: "→ guter Zwischenschritt", bg: "#eef0fe", fg: "#4f46e5" },
  incorrect: { label: "✗ noch nicht – bleib dran", bg: "#fdecec", fg: "#c0392b" },
};

function Bubble({ role, verifyStatus, children }) {
  const tutor = role === "tutor";
  const chip = !tutor && VERIFY_CHIP[verifyStatus];
  return (
    <div style={{ alignSelf: tutor ? "flex-start" : "flex-end", maxWidth: "78%", display: "flex", flexDirection: "column", alignItems: tutor ? "flex-start" : "flex-end", gap: 4 }}>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 8 }}>
        {tutor && (
          <span aria-hidden style={{ flex: "0 0 26px", width: 26, height: 26, borderRadius: "50%", background: "#eef0fe", color: "#4f46e5", display: "grid", placeItems: "center", fontSize: 13, fontWeight: 800, border: "1px solid #e0e2fb" }}>∑</span>
        )}
        <div
          className="popin"
          style={{
            background: tutor ? "#fff" : "#6366f1",
            color: tutor ? "#1a1c22" : "#fff",
            border: tutor ? "1px solid #e7e8ee" : "none",
            borderRadius: 18,
            borderBottomLeftRadius: tutor ? 5 : 18,
            borderBottomRightRadius: tutor ? 18 : 5,
            boxShadow: tutor ? "0 1px 2px rgba(40,40,90,.05),0 6px 16px rgba(40,40,90,.06)" : "none",
            padding: tutor ? "12px 16px" : "11px 16px",
            fontSize: 14,
            lineHeight: 1.5,
            whiteSpace: "pre-wrap",
          }}
        >
          {children}
        </div>
      </div>
      {chip && (
        <span className="verify-chip" style={{ fontSize: 11, fontWeight: 700, borderRadius: 999, padding: "3px 10px", background: chip.bg, color: chip.fg }}>
          {chip.label}
        </span>
      )}
    </div>
  );
}

// Konfetti-Regen beim Lösen (rein dekorativ, respektiert prefers-reduced-motion)
const CONFETTI_COLORS = ["#6366f1", "#8b8ef7", "#1a7f3c", "#8be0a4", "#f2b93b", "#e878a8"];
function Confetti() {
  const pieces = Array.from({ length: 28 }, (_, i) => ({
    left: `${(i * 37 + 13) % 100}%`,
    delay: `${(i % 7) * 0.12}s`,
    dur: `${1.6 + (i % 5) * 0.22}s`,
    color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
  }));
  return (
    <div aria-hidden style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none", zIndex: 15 }}>
      {pieces.map((p, i) => (
        <span key={i} className="confetti-piece" style={{ left: p.left, background: p.color, animationDuration: p.dur, animationDelay: p.delay }} />
      ))}
    </div>
  );
}

export default function Lernen() {
  const { attemptId } = useParams();
  const nav = useNavigate();
  const shell = useShell();
  const [state, setState] = useState(null); // {attempt, messages, exercise}
  const [streaming, setStreaming] = useState("");
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [celebrate, setCelebrate] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const chatRef = useRef(null);
  // Jeder Attempt-Wechsel/Send bekommt eine Token-Nummer; abgelaufene Antworten
  // (Race beim Aufgabenwechsel waehrend des Streamens) werden verworfen.
  const reqToken = useRef(0);
  const abortRef = useRef(null);

  const nearBottom = () => {
    const el = chatRef.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 120;
  };
  const scrollDown = useCallback((force = true) => {
    requestAnimationFrame(() => {
      if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
    });
  }, []);

  const load = useCallback(async (token) => {
    if (!attemptId) return null;
    try {
      const s = await api.get(`/api/attempts/${attemptId}`);
      if (token !== undefined && token !== reqToken.current) return null; // veraltet
      setState(s);
      setLoadError(false);
      scrollDown();
      return s;
    } catch {
      if (token !== undefined && token !== reqToken.current) return null;
      setState(null);
      setLoadError(true);
      return null;
    }
  }, [attemptId, scrollDown]);

  useEffect(() => {
    // Attempt gewechselt: laufenden Stream abbrechen, Token invalidieren, neu laden.
    reqToken.current += 1;
    if (abortRef.current) abortRef.current.abort();
    setStreaming("");
    setBusy(false);
    setState(null);
    setLoadError(false);
    load();
  }, [load]);

  useEffect(() => {
    if (nearBottom()) scrollDown();
  }, [streaming, state]);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    const myToken = ++reqToken.current;
    const myAttempt = attemptId;
    const controller = new AbortController();
    abortRef.current = controller;
    setInput("");
    setBusy(true);
    // Schüler-Bubble sofort optimistisch anzeigen
    setState((s) => (s ? { ...s, messages: [...s.messages, { id: `tmp-${Date.now()}`, role: "student", text }] } : s));
    setStreaming("");
    scrollDown();
    try {
      const res = await fetch(`${BASE}/api/attempts/${myAttempt}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ text }),
        signal: controller.signal,
      });
      if (res.status === 401) {
        await api.get("/api/auth/me").catch(() => {}); // loest globalen Logout aus, falls Session weg
        if (myToken === reqToken.current) {
          // Session noch gueltig (Race) -> Fehlerhinweis statt stummer Nachricht
          setState((s) => (s ? { ...s, messages: [...s.messages, { id: `err-${Date.now()}`, role: "tutor", text: "Ups, das hat nicht geklappt. Versuch es nochmal." }] } : s));
        }
        return;
      }
      if (!res.ok || !res.body) throw new Error("Fehler beim Senden");
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let acc = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        if (myToken !== reqToken.current) return; // Aufgabe gewechselt -> Antwort verwerfen
        acc += dec.decode(value, { stream: true });
        setStreaming(acc);
        if (nearBottom()) scrollDown();
      }
      if (myToken !== reqToken.current) return;
      setStreaming("");
      const wasSolved = state?.attempt?.solved;
      const fresh = await load(myToken); // echte Nachrichten + Leiter-Zustand nachladen
      if (myToken !== reqToken.current) return;
      shell.reloadQuota?.();
      if (!wasSolved) {
        shell.reloadTopics?.(); // Fortschritt in Sidebar/Grid aktualisieren
        // frisch gelöst -> Konfetti 🎉 (ausser reduced motion)
        if (fresh?.attempt?.solved && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
          setCelebrate(true);
          setTimeout(() => setCelebrate(false), 3200);
        }
      }
    } catch (e) {
      if (controller.signal.aborted || myToken !== reqToken.current) return; // bewusst abgebrochen
      setStreaming("");
      setState((s) => (s ? { ...s, messages: [...s.messages, { id: `err-${Date.now()}`, role: "tutor", text: "Ups, da ging etwas schief. Versuch es nochmal." }] } : s));
    } finally {
      if (myToken === reqToken.current) setBusy(false);
    }
  }

  // Attempt-Load fehlgeschlagen (geloescht / fremd / Server weg) -> klarer Fehler
  if (attemptId && loadError) {
    return (
      <div style={{ flex: 1, background: "#f6f7fb", display: "grid", placeItems: "center", padding: 24, height: "100%" }}>
        <div style={{ textAlign: "center", maxWidth: 380 }}>
          <div style={{ fontSize: 34, marginBottom: 10 }}>🔍</div>
          <div style={{ fontSize: 17, fontWeight: 800, marginBottom: 6 }}>Session nicht gefunden</div>
          <div style={{ fontSize: 14, color: "#6b7280", marginBottom: 18 }}>
            Diese Übungssession gibt es nicht (mehr). Starte eine neue Aufgabe.
          </div>
          <button onClick={() => shell.openNewTask()} className="btn-primary" style={{ padding: "12px 20px", borderRadius: 12, fontSize: 14 }}>
            + Neue Aufgabe
          </button>
        </div>
      </div>
    );
  }

  // Attempt gewählt, wird geladen -> dezenter Ladehinweis (kein Empty-State-Flackern)
  if (attemptId && !state) {
    return (
      <div style={{ flex: 1, background: "#f6f7fb", display: "grid", placeItems: "center", height: "100%", color: "#9aa0ab", fontSize: 14 }}>
        lädt …
      </div>
    );
  }

  // Kein Attempt gewählt -> Empty State
  if (!attemptId || !state) {
    return (
      <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, padding: "14px 22px", borderBottom: "1px solid #eef0f3" }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700 }}>Lernen</div>
            <div style={{ fontSize: 12, color: "#9aa0ab" }}>Schritt für Schritt zur Lösung</div>
          </div>
          <Ladder level={0} />
        </div>
        <div style={{ flex: 1, background: "#f6f7fb", display: "grid", placeItems: "center", padding: 24 }}>
          <div style={{ textAlign: "center", maxWidth: 420 }}>
            <div style={{ width: 64, height: 64, borderRadius: 18, background: "#eef0fe", color: "#4f46e5", fontSize: 28, display: "grid", placeItems: "center", margin: "0 auto 16px" }}>✎</div>
            <div style={{ fontSize: 18, fontWeight: 800, marginBottom: 6 }}>Bereit zum Üben?</div>
            <div style={{ fontSize: 14, color: "#6b7280", marginBottom: 20, lineHeight: 1.55 }}>
              Leg eine neue Aufgabe an – tippe sie ab oder fotografiere sie. Ich verrate dir die Lösung nie direkt, sondern helfe dir Stufe für Stufe.
            </div>
            <button onClick={() => shell.openNewTask()} className="btn-primary" style={{ padding: "13px 22px", borderRadius: 12, fontSize: 15 }}>
              + Neue Aufgabe
            </button>
          </div>
        </div>
      </div>
    );
  }

  const { attempt, exercise } = state;
  const topicName = shell.topics?.find((t) => t.id === exercise.topic_id)?.name || "Aufgabe";

  async function retry() {
    if (busy) return;
    setBusy(true);
    try {
      const st = await api.post(`/api/exercises/${exercise.id}/attempts`, {});
      nav(`/app/lernen/${st.attempt.id}`);
    } catch (e) {
      setState((s) => (s ? { ...s, messages: [...s.messages, { id: `err-${Date.now()}`, role: "tutor", text: e.message }] } : s));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", position: "relative" }}>
      {celebrate && <Confetti />}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, padding: "14px 22px", borderBottom: "1px solid #eef0f3", flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700 }}>{topicName}</div>
          <div style={{ fontSize: 12, color: "#9aa0ab" }}>
            {attempt.solved ? "gelöst · gut gemacht" : "Schritt für Schritt"} · {attempt.own_attempts} eigene Versuche
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {attempt.solved && (
            <button onClick={retry} className="btn-ghost" style={{ fontSize: 12, padding: "8px 14px", borderRadius: 999 }}>
              ↻ Nochmal üben
            </button>
          )}
          <Ladder level={attempt.hint_level} solved={attempt.solved} />
        </div>
      </div>

      <div ref={chatRef} style={{ flex: 1, background: "#f6f7fb", padding: "22px 24px", display: "flex", flexDirection: "column", gap: 14, overflowY: "auto" }}>
        {state.messages.map((m) => (
          <Bubble key={m.id} role={m.role} verifyStatus={m.verification_status}>
            <MathText text={m.text} />
          </Bubble>
        ))}
        {streaming && (
          <Bubble role="tutor">
            <MathText text={streaming} />
          </Bubble>
        )}
        {busy && !streaming && (
          <Bubble role="tutor">
            <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
          </Bubble>
        )}
        {attempt.solved && !busy && !streaming && (
          <div className="solved-banner" style={{ alignSelf: "center", display: "flex", alignItems: "center", gap: 8, background: "#e8f6ec", border: "1px solid #cde7d6", color: "#1a7f3c", borderRadius: 999, padding: "8px 18px", fontSize: 13, fontWeight: 700 }}>
            🎉 Aufgabe gelöst – stark!
            <button onClick={retry} style={{ border: "none", background: "transparent", color: "#1a7f3c", fontWeight: 700, fontSize: 13, textDecoration: "underline", cursor: "pointer", padding: 0 }}>
              nochmal üben
            </button>
            <button onClick={() => shell.openNewTask(exercise.topic_id ?? undefined)} style={{ border: "none", background: "transparent", color: "#1a7f3c", fontWeight: 700, fontSize: 13, textDecoration: "underline", cursor: "pointer", padding: 0 }}>
              neue Aufgabe
            </button>
          </div>
        )}
      </div>

      <div style={{ padding: "14px 18px", background: "#fff", borderTop: "1px solid #eef0f3" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, border: "1px solid #d2d4dd", borderRadius: 24, padding: "7px 8px 7px 14px" }}>
          <span onClick={() => shell.openNewTask()} title="Foto-Aufgabe" style={{ color: "#b6bcc6", fontSize: 15, cursor: "pointer" }}>📷</span>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Schreib deinen nächsten Schritt …"
            style={{ flex: 1, border: "none", outline: "none", fontSize: 13, color: "#1a1c22", background: "transparent", paddingLeft: 4 }}
          />
          <button onClick={send} disabled={busy} style={{ width: 34, height: 34, borderRadius: "50%", background: "#6366f1", color: "#fff", border: "none", display: "grid", placeItems: "center", fontSize: 15, boxShadow: "0 2px 8px rgba(99,102,241,.35)", opacity: busy ? 0.6 : 1 }}>↑</button>
        </div>
      </div>
    </div>
  );
}
