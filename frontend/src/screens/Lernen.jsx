import { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, getToken } from "../lib/api.js";
import { useShell } from "../components/AppShell.jsx";
import DrawPad from "../components/DrawPad.jsx";
import MathText from "../lib/MathText.jsx";
import MathFigure from "../components/MathFigure.jsx";

const BASE = import.meta.env.VITE_API_BASE || "";

const STUFEN_LABEL = {
  1: "Stufe 1: Aktivierende Frage",
  2: "Stufe 2: Kleiner Tipp",
  3: "Stufe 3: Teilschritt vorgemacht",
  4: "Stufe 4: Volle Lösung",
};

function Ladder({ level, solved, ownAttempts = 0 }) {
  // Nach 2 echten eigenen Versuchen auf hoher Stufe ist die Loesung verdient
  const unlocked = !solved && level >= 3 && ownAttempts >= 2;
  const accent = solved || unlocked ? "#1a7f3c" : "#4f46e5";
  const bg = solved || unlocked ? "#e8f6ec" : "#eef0fe";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, background: bg, borderRadius: 999, padding: "6px 14px", transition: "background .3s" }}>
      <span style={{ fontSize: 11, fontWeight: 700, color: accent }}>HILFE</span>
      {[1, 2, 3, 4].map((i) => (
        <span
          key={i}
          title={STUFEN_LABEL[i]}
          className={`ladder-dot ${i <= level ? "filled" : ""}`}
          style={{
            width: 9, height: 9, borderRadius: "50%", display: "inline-block", cursor: "help",
            background: i <= level ? accent : "#fff",
            border: i <= level ? "none" : `1.5px solid ${solved || unlocked ? "#bfe3cb" : "#c9ccf6"}`,
          }}
        />
      ))}
      <span style={{ fontSize: 11, fontWeight: 600, color: accent }}>
        {solved ? "Gelöst 🎉" : unlocked ? "🔓 Lösung verfügbar" : `Stufe ${Math.max(level, 0)}/4`}
      </span>
    </div>
  );
}

// Tutor-Text mit eingebetteten Skizzen: [[FIGUR]]{json}[[/FIGUR]]-Bloecke
// werden zu praezisen MathFigure-Vorlagen, der Rest bleibt MathText.
const FIG_RE = /\[\[FIGUR\]\]([\s\S]*?)\[\[\/FIGUR\]\]/g;

// Tolerant parsen: falls das Modell Fuellsel vor das JSON setzt (z.B. ein
// woertlich kopiertes «{json}»), das echte Objekt herausfischen.
function parseSpec(raw) {
  const t = (raw || "").trim();
  try {
    return JSON.parse(t);
  } catch { /* weiter unten retten */ }
  const start = t.indexOf('{"');
  const end = t.lastIndexOf("}");
  if (start !== -1 && end > start) {
    try {
      return JSON.parse(t.slice(start, end + 1));
    } catch { /* nicht rettbar */ }
  }
  return null;
}

function TutorContent({ text, streaming = false }) {
  let src = text || "";
  let drawing = false;
  if (streaming) {
    // unvollstaendiger Block am Ende: ausblenden statt rohes JSON zu zeigen
    const open = src.lastIndexOf("[[FIGUR]]");
    if (open !== -1 && src.indexOf("[[/FIGUR]]", open) === -1) {
      src = src.slice(0, open);
      drawing = true;
    }
  }
  const parts = [];
  let last = 0;
  let i = 0;
  const re = new RegExp(FIG_RE.source, "g");
  let m;
  while ((m = re.exec(src)) !== null) {
    if (m.index > last) parts.push(<MathText key={`t${i++}`} text={src.slice(last, m.index)} />);
    const spec = parseSpec(m[1]); // kaputtes JSON: Skizze still weglassen
    if (spec) parts.push(<MathFigure key={`f${i++}`} spec={spec} />);
    last = re.lastIndex;
  }
  if (last < src.length) parts.push(<MathText key={`t${i++}`} text={src.slice(last)} />);
  if (drawing) parts.push(<span key="draw" style={{ display: "block", fontSize: 12.5, color: "#9aa0ab", marginTop: 6 }}>✏️ Skizze wird gezeichnet …</span>);
  return <>{parts}</>;
}

// Was diese Tutor-Antwort ist – macht die Hilfe-Stufen im Chat sichtbar.
const STAGE_TAG = {
  1: { label: "💬 Frage zum Nachdenken", bg: "#eef0fe", fg: "#4f46e5" },
  2: { label: "💡 Kleiner Tipp", bg: "#fdf3e6", fg: "#a05c12" },
  3: { label: "👣 Teilschritt vorgemacht", bg: "#e7f0fd", fg: "#1d4ed8" },
  4: { label: "🔓 Ganzer Lösungsweg", bg: "#e8f6ec", fg: "#1a7f3c" },
};

// Visuelles Feedback zur SymPy-Prüfung unter der Schüler-Bubble (nie die Lösung)
const VERIFY_CHIP = {
  correct: { label: "✓ stimmt!", bg: "#e8f6ec", fg: "#1a7f3c" },
  partial: { label: "→ guter Zwischenschritt", bg: "#eef0fe", fg: "#4f46e5" },
  incorrect: { label: "✗ noch nicht – bleib dran", bg: "#fdecec", fg: "#c0392b" },
};

function Bubble({ role, verifyStatus, hintLevel, children }) {
  const tutor = role === "tutor";
  const chip = !tutor && VERIFY_CHIP[verifyStatus];
  const tag = tutor && STAGE_TAG[hintLevel];
  // Feedback direkt an der Bubble: richtig = gruen + ✓-Badge; falsch = weicher
  // roter Ring (bewusst NICHT rot gefuellt – soll nicht bestrafend wirken).
  const correct = !tutor && verifyStatus === "correct";
  const incorrect = !tutor && verifyStatus === "incorrect";
  return (
    <div style={{ alignSelf: tutor ? "flex-start" : "flex-end", maxWidth: "78%", display: "flex", flexDirection: "column", alignItems: tutor ? "flex-start" : "flex-end", gap: 4 }}>
      {tag && (
        <span style={{ marginLeft: 34, fontSize: 10.5, fontWeight: 700, borderRadius: 999, padding: "2px 9px", background: tag.bg, color: tag.fg }}>
          {tag.label}
        </span>
      )}
      <div style={{ display: "flex", alignItems: "flex-end", gap: 8, position: "relative" }}>
        {tutor && (
          <span aria-hidden style={{ flex: "0 0 26px", width: 26, height: 26, borderRadius: "50%", background: "#eef0fe", color: "#4f46e5", display: "grid", placeItems: "center", fontSize: 13, fontWeight: 800, border: "1px solid #e0e2fb" }}>∑</span>
        )}
        <div
          className="popin"
          style={{
            background: tutor ? "#fff" : correct ? "#1f9048" : "#6366f1",
            color: tutor ? "#1a1c22" : "#fff",
            border: tutor ? "1px solid #e7e8ee" : "none",
            borderRadius: 18,
            borderBottomLeftRadius: tutor ? 5 : 18,
            borderBottomRightRadius: tutor ? 18 : 5,
            boxShadow: tutor
              ? "0 1px 2px rgba(40,40,90,.05),0 6px 16px rgba(40,40,90,.06)"
              : incorrect
                ? "0 0 0 2.5px #f3c1bc"
                : "none",
            padding: tutor ? "12px 16px" : "11px 16px",
            fontSize: 14.5,
            lineHeight: 1.6,
            whiteSpace: "pre-wrap",
          }}
        >
          {children}
        </div>
        {correct && (
          <span aria-hidden style={{ position: "absolute", top: -8, right: -8, width: 21, height: 21, borderRadius: "50%", background: "#1a7f3c", color: "#fff", fontSize: 11, fontWeight: 800, display: "grid", placeItems: "center", border: "2px solid #f6f7fb" }}>✓</span>
        )}
      </div>
      {chip && (
        <span className="verify-chip" style={{ fontSize: 11, fontWeight: 700, borderRadius: 999, padding: "3px 10px", background: chip.bg, color: chip.fg }}>
          {chip.label}
        </span>
      )}
    </div>
  );
}

// Schnell-Antworten: ein Tipp genuegt – junge Schueler muessen nicht tippen.
function QuickReplies({ solved, unlocked, onSend, onNew, onVariant }) {
  const items = solved
    ? [
        ...(onVariant ? [{ label: "🔁 Nochmal so eine", act: onVariant, accent: true }] : []),
        { label: "🎯 Erklär mir den Weg nochmal", act: () => onSend("Erklär mir den Lösungsweg nochmal Schritt für Schritt.") },
        { label: "➕ Neue Aufgabe", act: onNew },
      ]
    : [
        // verdient nach 2 eigenen Versuchen: die Loesung ist jetzt abholbar
        ...(unlocked ? [{ label: "🔓 Zeig mir die ganze Lösung", act: () => onSend("Zeig mir die Lösung bitte."), accent: true }] : []),
        { label: "🤔 Ich verstehe es nicht", act: () => onSend("Ich verstehe es nicht.") },
        { label: "💡 Gib mir einen Tipp", act: () => onSend("Gib mir bitte einen Tipp.") },
        { label: "👣 Zeig mir den ersten Schritt", act: () => onSend("Zeig mir bitte den ersten Schritt.") },
        // andere DARSTELLUNG derselben Stufe – Hilfe-Stufe steigt dabei nicht
        { label: "🎨 Mit Skizze", act: () => onSend("Kannst du es mir mit einer Skizze zeigen?") },
        { label: "🍕 Mit Alltagsbeispiel", act: () => onSend("Erklär es mir mit einem Beispiel aus dem Alltag.") },
        { label: "🔢 Mit Zahlen statt x", act: () => onSend("Erklär es mir mit konkreten Zahlen statt mit x.") },
        { label: "🐢 Erklär es einfacher", act: () => onSend("Kannst du es mir einfacher erklären?") },
      ];
  return (
    <div style={{ display: "flex", gap: 8, overflowX: "auto", padding: "0 2px 9px", WebkitOverflowScrolling: "touch" }}>
      {items.map((it) => (
        <button
          key={it.label}
          onClick={it.act}
          style={{
            flex: "0 0 auto", borderRadius: 999, padding: "8px 14px", fontSize: 12.5, fontWeight: 600, whiteSpace: "nowrap",
            border: it.accent ? "1px solid #bfe3cb" : "1px solid #dcdff5",
            background: it.accent ? "#e8f6ec" : "#f8f8ff",
            color: it.accent ? "#1a7f3c" : "#4f46e5",
          }}
        >
          {it.label}
        </button>
      ))}
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
  const [drawOpen, setDrawOpen] = useState(false);
  const [variantBusy, setVariantBusy] = useState(false);
  const [lightbox, setLightbox] = useState(false); // Aufgaben-Bild gross anzeigen
  const [showTaskText, setShowTaskText] = useState(false); // Text unter Foto-Aufgabe
  const [stats, setStats] = useState(null); // {serie_tage, geloest_woche}
  const inputRef = useRef(null);
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

  // Motivations-Zahlen (Serie/Woche) – einmal laden, nach jedem Lösen frisch
  useEffect(() => {
    api.get("/api/stats/mini").then(setStats).catch(() => setStats(null));
  }, [attemptId, state?.attempt?.solved]);

  async function send(overrideText) {
    // onClick={send} liefert ein Event-Objekt als erstes Argument – nur echte
    // Strings (Schnell-Antworten) zaehlen als Override.
    const text = (typeof overrideText === "string" ? overrideText : input).trim();
    if (!text || busy) return;
    const myToken = ++reqToken.current;
    const myAttempt = attemptId;
    const controller = new AbortController();
    abortRef.current = controller;
    if (typeof overrideText !== "string") setInput(""); // getippten Entwurf nicht wegwerfen
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
      if (res.status === 402) {
        // Guthaben leer: Nachricht wurde NICHT gesendet – optimistische Bubble
        // entfernen, Entwurf zurueckgeben und freundlich zum Laden einladen.
        if (myToken === reqToken.current) {
          setState((s) => (s ? { ...s, messages: [...s.messages.filter((m) => !String(m.id).startsWith("tmp-")), { id: `quota-${Date.now()}`, role: "tutor", kind: "quota", text: "" }] } : s));
          if (typeof overrideText !== "string") setInput(text);
          shell.reloadQuota?.();
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
          {/* keine Hilfe-Anzeige: sie gilt pro Aufgabe – hier ist keine offen */}
        </div>
        <div style={{ flex: 1, background: "#f6f7fb", display: "grid", placeItems: "center", padding: 24 }}>
          <div style={{ textAlign: "center", maxWidth: 420 }}>
            <div style={{ width: 64, height: 64, borderRadius: 18, background: "#eef0fe", color: "#4f46e5", fontSize: 28, display: "grid", placeItems: "center", margin: "0 auto 16px" }}>✎</div>
            <div style={{ fontSize: 18, fontWeight: 800, marginBottom: 6 }}>Bereit zum Üben?</div>
            {stats?.serie_tage >= 2 && (
              <div style={{ display: "flex", gap: 8, justifyContent: "center", marginBottom: 12 }}>
                <span style={{ fontSize: 12.5, fontWeight: 700, color: "#d97706", background: "#fdf3e6", border: "1px solid #f2ddb8", borderRadius: 999, padding: "5px 13px" }}>🔥 {stats.serie_tage} Tage in Folge</span>
              </div>
            )}
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

  // «Nochmal so eine»: KI erzeugt eine Variante (gleicher Typ, andere Zahlen)
  async function makeVariant() {
    if (busy || variantBusy) return;
    setVariantBusy(true);
    try {
      const st = await api.post(`/api/exercises/${exercise.id}/variante`, {});
      shell.reloadQuota?.();
      shell.reloadTopics?.();
      nav(`/app/lernen/${st.attempt.id}`);
    } catch (e) {
      if (e.status === 402) {
        setState((s) => (s ? { ...s, messages: [...s.messages, { id: `quota-${Date.now()}`, role: "tutor", kind: "quota", text: "" }] } : s));
      } else {
        setState((s) => (s ? { ...s, messages: [...s.messages, { id: `err-${Date.now()}`, role: "tutor", text: e.message }] } : s));
      }
    } finally {
      setVariantBusy(false);
    }
  }

  // Mathe-Tastatur: Symbol an der Cursor-Position einfuegen
  function insertSymbol(snippet, cursorOffset) {
    const el = inputRef.current;
    const start = el?.selectionStart ?? input.length;
    const end = el?.selectionEnd ?? input.length;
    const next = input.slice(0, start) + snippet + input.slice(end);
    setInput(next);
    requestAnimationFrame(() => {
      if (!el) return;
      el.focus();
      const pos = start + (cursorOffset ?? snippet.length);
      el.setSelectionRange(pos, pos);
    });
  }

  const inputLooksMathy = /\d/.test(input) && /[+\-*/^=()]|sqrt|pi/.test(input);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", position: "relative" }}>
      {celebrate && <Confetti />}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, padding: "14px 22px", borderBottom: "1px solid #eef0f3", flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700 }}>{topicName}</div>
          <div style={{ fontSize: 12, color: "#9aa0ab" }}>
            {attempt.solved ? "gelöst · gut gemacht" : "Schritt für Schritt"}
            {stats?.serie_tage >= 2 && <span style={{ color: "#d97706", fontWeight: 700 }}> · 🔥 {stats.serie_tage} Tage in Folge</span>}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {attempt.solved && (
            <button onClick={retry} className="btn-ghost" style={{ fontSize: 12, padding: "8px 14px", borderRadius: 999 }}>
              ↻ Nochmal üben
            </button>
          )}
          {/* Hilfe-Anzeige gilt PRO Aufgabe: erst zeigen, wenn in dieser
              Aufgabe Hilfe im Spiel ist (oder sie geloest wurde) – ein
              permanentes «Stufe 0/4» sagt nichts aus. */}
          {(attempt.solved || attempt.hint_level >= 1) && (
            <Ladder level={attempt.hint_level} solved={attempt.solved} ownAttempts={attempt.own_attempts} />
          )}
        </div>
      </div>

      {/* Aufgabe immer sichtbar – Schueler muessen nie hochscrollen.
          Foto-Aufgaben: das BILD ist die Aufgabe (Text nur auf Wunsch). */}
      <div style={{ background: "#f6f7fb", padding: "12px 24px 0" }}>
        <div style={{ background: "#f8f8ff", border: "1px solid #e0e2fb", borderRadius: 14, padding: "10px 16px", maxHeight: exercise.image_path ? 270 : 130, overflowY: "auto" }}>
          <div style={{ fontSize: 10.5, fontWeight: 800, letterSpacing: ".07em", color: "#4f46e5", marginBottom: 3 }}>DEINE AUFGABE</div>
          {exercise.image_path ? (
            <>
              <img
                src={`${BASE}${exercise.image_path}`}
                alt="Aufgaben-Bild"
                title="🔍 vergrössern"
                onClick={() => setLightbox(true)}
                style={{ display: "block", maxWidth: "100%", maxHeight: 190, borderRadius: 10, border: "1px solid #e0e2fb", cursor: "zoom-in" }}
              />
              {exercise.text && exercise.text !== "(Aufgabe auf dem Foto)" && (
                <>
                  <button
                    onClick={() => setShowTaskText(!showTaskText)}
                    style={{ border: "none", background: "transparent", color: "#6b7280", fontSize: 12, fontWeight: 600, cursor: "pointer", padding: "6px 0 2px" }}
                  >
                    Aufgabentext {showTaskText ? "ausblenden ▴" : "anzeigen ▾"}
                  </button>
                  {showTaskText && (
                    <div style={{ fontSize: 13.5, lineHeight: 1.55, whiteSpace: "pre-wrap", color: "#4b4f5c" }}>
                      <MathText text={exercise.text} />
                    </div>
                  )}
                </>
              )}
            </>
          ) : (
            <div style={{ fontSize: 14.5, lineHeight: 1.55, whiteSpace: "pre-wrap" }}>
              <MathText text={exercise.text} />
            </div>
          )}
        </div>
      </div>

      <div ref={chatRef} style={{ flex: 1, background: "#f6f7fb", padding: "18px 24px 22px", display: "flex", flexDirection: "column", gap: 16, overflowY: "auto" }}>
        {(() => {
          const out = [];
          let lastLevel = 0;
          for (const m of state.messages) {
            if (m.role === "tutor" && m.hint_level) {
              if (lastLevel && m.hint_level > lastLevel) {
                out.push(
                  <div key={`lvl-${m.id}`} style={{ alignSelf: "center", fontSize: 11, fontWeight: 700, color: "#4f46e5", background: "#eef0fe", border: "1px solid #e0e2fb", borderRadius: 999, padding: "4px 13px" }}>
                    ⬆️ Nächste Hilfe-Stufe
                  </div>
                );
              }
              lastLevel = m.hint_level;
            }
            if (m.kind === "quota") {
              out.push(
                <div key={m.id} style={{ alignSelf: "flex-start", maxWidth: 420, background: "#fffaf0", border: "1px solid #f0e2c4", borderRadius: 16, padding: "14px 16px" }}>
                  <div style={{ fontSize: 13.5, fontWeight: 700, marginBottom: 4 }}>⚡ Dein Guthaben ist aufgebraucht</div>
                  <div style={{ fontSize: 13, color: "#6b7280", lineHeight: 1.5, marginBottom: 10 }}>
                    Deine Nachricht wurde nicht gesendet – sie steht noch im Eingabefeld.
                    Lad Tokens oder warte auf die Gratis-Tokens vom nächsten Monat.
                  </div>
                  <button onClick={() => nav("/app/preise")} className="btn-primary" style={{ border: "none", borderRadius: 10, padding: "9px 14px", fontSize: 13 }}>
                    Tokens laden →
                  </button>
                </div>
              );
              continue;
            }
            out.push(
              <Bubble key={m.id} role={m.role} verifyStatus={m.verification_status} hintLevel={m.role === "tutor" ? m.hint_level : null}>
                {m.role === "tutor" ? <TutorContent text={m.text} /> : <MathText text={m.text} />}
              </Bubble>
            );
          }
          return out;
        })()}
        {streaming && (
          <Bubble role="tutor">
            <TutorContent text={streaming} streaming />
          </Bubble>
        )}
        {busy && !streaming && (
          <Bubble role="tutor">
            <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
          </Bubble>
        )}
        {attempt.solved && !busy && !streaming && (
          <div className="solved-banner" style={{ alignSelf: "center", display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", justifyContent: "center", background: "#e8f6ec", border: "1px solid #cde7d6", color: "#1a7f3c", borderRadius: 999, padding: "8px 18px", fontSize: 13, fontWeight: 700 }}>
            🎉 Aufgabe gelöst – stark!
            <button onClick={makeVariant} disabled={variantBusy} style={{ border: "none", background: "transparent", color: "#1a7f3c", fontWeight: 700, fontSize: 13, textDecoration: "underline", cursor: "pointer", padding: 0 }}>
              {variantBusy ? "erstelle Variante …" : "🔁 nochmal so eine"}
            </button>
            <button onClick={retry} style={{ border: "none", background: "transparent", color: "#1a7f3c", fontWeight: 700, fontSize: 13, textDecoration: "underline", cursor: "pointer", padding: 0 }}>
              nochmal üben
            </button>
            <button onClick={() => shell.openNewTask(exercise.topic_id ?? undefined)} style={{ border: "none", background: "transparent", color: "#1a7f3c", fontWeight: 700, fontSize: 13, textDecoration: "underline", cursor: "pointer", padding: 0 }}>
              neue Aufgabe
            </button>
          </div>
        )}
      </div>

      <div style={{ padding: "12px 18px 14px", background: "#fff", borderTop: "1px solid #eef0f3" }}>
        {!busy && (
          <QuickReplies
            solved={attempt.solved}
            unlocked={attempt.hint_level >= 3 && attempt.own_attempts >= 2}
            onSend={(t) => send(t)}
            onNew={() => shell.openNewTask(exercise.topic_id ?? undefined)}
            onVariant={makeVariant}
          />
        )}
        {inputLooksMathy && (
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, background: "#f8f8ff", border: "1px solid #e0e2fb", borderRadius: 12, padding: "7px 14px", marginBottom: 8, fontSize: 14, overflowX: "auto" }}>
            <span style={{ fontSize: 10.5, fontWeight: 800, letterSpacing: ".06em", color: "#9aa0ab", flex: "0 0 auto" }}>SO SIEHT'S AUS</span>
            <MathText text={input} />
          </div>
        )}
        <div style={{ display: "flex", gap: 6, overflowX: "auto", paddingBottom: 8, WebkitOverflowScrolling: "touch" }}>
          {[
            ["½", "/", 1],
            ["x²", "^2"],
            ["√", "sqrt()", 5],
            ["×", "*"],
            ["÷", "/"],
            ["( )", "()", 1],
            ["=", "="],
            ["π", "pi"],
          ].map(([label, snippet, offset]) => (
            <button
              key={label}
              type="button"
              onMouseDown={(e) => e.preventDefault() /* Fokus bleibt im Eingabefeld */}
              onClick={() => insertSymbol(snippet, offset)}
              style={{ flex: "0 0 auto", minWidth: 40, borderRadius: 10, padding: "7px 10px", fontSize: 14, fontWeight: 600, border: "1px solid #e7e8ee", background: "#fbfbfd", color: "#1a1c22", cursor: "pointer" }}
            >
              {label}
            </button>
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, border: "1px solid #d2d4dd", borderRadius: 24, padding: "7px 8px 7px 14px" }}>
          <span onClick={() => shell.openNewTask()} title="Foto-Aufgabe" style={{ color: "#b6bcc6", fontSize: 15, cursor: "pointer" }}>📷</span>
          <span onClick={() => setDrawOpen(true)} title="Mit dem Stift schreiben" style={{ color: "#b6bcc6", fontSize: 15, cursor: "pointer" }}>✍️</span>
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Schreib deinen nächsten Schritt …"
            style={{ flex: 1, border: "none", outline: "none", fontSize: 13, color: "#1a1c22", background: "transparent", paddingLeft: 4 }}
          />
          <button onClick={send} disabled={busy} style={{ width: 34, height: 34, borderRadius: "50%", background: "#6366f1", color: "#fff", border: "none", display: "grid", placeItems: "center", fontSize: 15, boxShadow: "0 2px 8px rgba(99,102,241,.35)", opacity: busy ? 0.6 : 1 }}>↑</button>
        </div>
      </div>

      {drawOpen && (
        <DrawPad
          onClose={() => setDrawOpen(false)}
          onResult={(text) => setInput((prev) => (prev.trim() ? `${prev.trim()} ${text}` : text))}
        />
      )}

      {lightbox && exercise.image_path && (
        <div
          onClick={() => setLightbox(false)}
          onKeyDown={(e) => e.key === "Escape" && setLightbox(false)}
          tabIndex={-1}
          ref={(el) => el?.focus()}
          style={{ position: "fixed", inset: 0, background: "rgba(15,15,30,.82)", zIndex: 60, display: "grid", placeItems: "center", padding: 20, cursor: "zoom-out" }}
        >
          <img
            src={`${BASE}${exercise.image_path}`}
            alt="Aufgaben-Bild gross"
            style={{ maxWidth: "92vw", maxHeight: "88vh", borderRadius: 14, boxShadow: "0 20px 60px rgba(0,0,0,.5)", background: "#fff" }}
          />
          <button
            onClick={() => setLightbox(false)}
            aria-label="Schliessen"
            style={{ position: "fixed", top: 18, right: 18, width: 38, height: 38, borderRadius: "50%", border: "none", background: "rgba(255,255,255,.92)", color: "#1a1c22", fontSize: 17, fontWeight: 700, cursor: "pointer" }}
          >
            ✕
          </button>
        </div>
      )}
    </div>
  );
}
