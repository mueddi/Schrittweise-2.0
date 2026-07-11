/* Demo-Modus: kompletter In-Browser-Ersatz fürs Backend.
 *
 * Wird nur geladen, wenn VITE_DEMO=1 (siehe main.jsx). Fängt window.fetch für
 * /api/* ab und bildet Auth, Themen, Aufgaben, Hinweis-Leiter-Chat (inkl.
 * Streaming), Kontingent und Eltern-Verknüpfung nach. Daten liegen in
 * localStorage – nichts verlässt den Browser. Der Tutor ist der gleiche
 * deterministische Mock wie im Backend ohne API-Key.
 */

const KEY = "sw_demo_v1";

function load() {
  try { return JSON.parse(localStorage.getItem(KEY)); } catch { return null; }
}
const db = load() || {
  seq: 1, users: [], magic: {}, topics: [], exercises: [], attempts: [], messages: [], links: [],
};
function save() { localStorage.setItem(KEY, JSON.stringify(db)); }
function nid() { return db.seq++; }
function now() { return new Date().toISOString(); }

// ---------------- Mathe-Verifikation (JS-Port des SymPy-Verifiers, linear & Co.) ----------------
function compile(exprSide) {
  let s = exprSide.trim()
    .replace(/−/g, "-").replace(/[·×]/g, "*").replace(/:/g, "/").replace(/,/g, ".")
    .replace(/\^/g, "**")
    .replace(/(\d)\s*([a-zA-Z(])/g, "$1*$2")     // 3x -> 3*x, 2( -> 2*(
    .replace(/([a-zA-Z)])\s*(\d)/g, "$1*$2")     // x2 -> x*2 (selten, aber konsistent)
    .replace(/\)\s*\(/g, ")*(");
  if (!/^[0-9a-zA-Z+\-*/().\s*]*$/.test(s.replace(/\*\*/g, ""))) return null;
  const vars = [...new Set(s.match(/[a-zA-Z]/g) || [])];
  if (vars.length > 1) return null;
  const v = vars[0] || "x";
  try {
    // eslint-disable-next-line no-new-func
    const f = new Function(v, `"use strict"; return (${s});`);
    f(1); // Probelauf
    return { f, v };
  } catch { return null; }
}

function solveRoots(lhs, rhs) {
  const L = compile(lhs), R = compile(rhs);
  if (!L || !R) return null;
  const g = (x) => L.f(x) - R.f(x);
  try {
    const roots = [];
    // linear? a*x + b
    const b = g(0), a = g(1) - b;
    const quadCheck = g(2) - (2 * a + b);
    if (Math.abs(quadCheck) < 1e-9) {
      if (Math.abs(a) > 1e-12) roots.push(-b / a);
      return { g, roots, variable: L.v || R.v };
    }
    // sonst: grob scannen + Bisektion
    let prev = g(-100);
    for (let x = -100; x <= 100; x += 0.25) {
      const cur = g(x + 0.25);
      if (Number.isFinite(prev) && Number.isFinite(cur) && prev * cur <= 0) {
        let lo = x, hi = x + 0.25;
        for (let i = 0; i < 60; i++) {
          const mid = (lo + hi) / 2;
          if (g(lo) * g(mid) <= 0) hi = mid; else lo = mid;
        }
        const r = (lo + hi) / 2;
        if (!roots.some((q) => Math.abs(q - r) < 1e-6)) roots.push(r);
      }
      prev = cur;
    }
    return { g, roots, variable: L.v || R.v };
  } catch { return null; }
}

function fmtNum(n) {
  const r = Math.round(n);
  return Math.abs(n - r) < 1e-9 ? String(r) : String(Math.round(n * 1000) / 1000);
}

function verify(exerciseExpr, message) {
  const res = { status: "unknown", solution: null, extracted: null };
  if (!exerciseExpr || !exerciseExpr.includes("=")) return res;
  const [lhs, rhs] = exerciseExpr.split("=");
  const solved = solveRoots(lhs, rhs);
  if (!solved || !solved.roots.length) return res;
  res.solution = solved.roots.map((r) => `${solved.variable} = ${fmtNum(r)}`).join(", ");

  const msg = message.replace(/−/g, "-").replace(/,/g, ".");
  const cands = [];
  if (msg.includes("=")) {
    cands.push(msg);
    // Mathe-Fragment um '=' aus Prosa ziehen
    const m = msg.match(/([0-9a-zA-Z+\-*/^().\s]+?)=\s*([0-9a-zA-Z+\-*/^().\s]+)/);
    if (m) {
      const lt = m[1].split(/\s+/).filter(Boolean);
      while (lt.length && /^[a-zA-Z]{2,}$/.test(lt[0])) lt.shift();
      const rt = [];
      for (const t of m[2].split(/\s+/).filter(Boolean)) {
        if (/^[a-zA-Z]{2,}$/.test(t)) break;
        rt.push(t);
      }
      if (lt.length && rt.length) cands.push(`${lt.join(" ")} = ${rt.join(" ")}`);
    }
  }
  const vm = msg.match(/(?<![0-9a-zA-Z])([a-zA-Z])\s*=\s*([-+]?\d+(?:\.\d+)?(?:\/\d+)?)/);
  if (vm) cands.push(`${vm[1]} = ${vm[2]}`);
  const nums = msg.match(/[-+]?\d+(?:\.\d+)?/g) || [];
  if (nums.length === 1 && !cands.length && msg.trim().split(/\s+/).length <= 3) cands.push(nums[0]);

  for (const cand of cands) {
    if (cand.includes("=")) {
      const [cl, cr] = cand.split("=");
      const clC = compile(cl), crC = compile(cr);
      if (!clC || !crC) continue;
      const clStr = cl.replace(/\s+/g, "");
      const isFinal = /^[a-zA-Z]$/.test(clStr) && Number.isFinite(Number(cr.trim().replace(/\s+/g, "")))
        || (/^[a-zA-Z]$/.test(clStr) && crC && !( `${cr}`.match(/[a-zA-Z]/)));
      if (isFinal) {
        const val = crC.f(0); // Konstante
        res.extracted = `${clStr} = ${fmtNum(val)}`;
        const hit = solved.roots.some((r) => Math.abs(r - val) < 1e-6);
        res.status = hit ? "correct" : "incorrect";
        return res;
      }
      // Umformungsschritt: erfüllen die Original-Lösungen die Kandidaten-Gleichung?
      try {
        const oL = compile(lhs), oR = compile(rhs);
        const samples = [0.7, 1.9, -2.3];
        // Nur die Aufgabe wiederholt (gleiche Seiten, evtl. vertauscht)? -> kein eigener Schritt
        const same = oL && oR && samples.every((x) => Math.abs(clC.f(x) - oL.f(x)) < 1e-6 && Math.abs(crC.f(x) - oR.f(x)) < 1e-6);
        const swapped = oL && oR && samples.every((x) => Math.abs(clC.f(x) - oR.f(x)) < 1e-6 && Math.abs(crC.f(x) - oL.f(x)) < 1e-6);
        if (same || swapped) { res.extracted = cand.trim(); res.status = "unknown"; return res; }
        const gc = (x) => clC.f(x) - crC.f(x);
        const allHold = solved.roots.every((r) => Math.abs(gc(r)) < 1e-6);
        // trivial wahr (0=0 für alle x)? Stichprobe
        const trivial = Math.abs(gc(solved.roots[0] + 1.234)) < 1e-6;
        res.extracted = cand.trim();
        res.status = allHold && !trivial ? "partial" : (allHold ? "unknown" : "incorrect");
        return res;
      } catch { continue; }
    }
    const val = Number(cand);
    if (Number.isFinite(val)) {
      res.extracted = cand;
      res.status = solved.roots.some((r) => Math.abs(r - val) < 1e-6) ? "correct" : "incorrect";
      return res;
    }
  }
  return res;
}

// Aus einem Aufgabentext eine pruefbare Gleichung ziehen («Löse 3x = 15» -> «3x = 15»)
function extractExpression(text) {
  if (!text || !text.includes("=")) return null;
  let t = text;
  const label = t.match(/^\s*[A-Za-zÀ-ÿ ]+:\s*(.+)$/);
  if (label && label[1].includes("=")) t = label[1];
  const norm = t.replace(/−/g, "-").replace(/·|×/g, "*").replace(/,/g, ".");
  const m = norm.match(/([0-9A-Za-z+\-*/^(). ]+)=\s*([0-9A-Za-z+\-*/^(). ]+)/);
  if (!m) return null;
  const rt = [];
  for (const tok of m[2].split(/\s+/).filter(Boolean)) {
    if (/^[A-Za-z]{2,}$/.test(tok)) break;
    rt.push(tok);
  }
  if (!rt.length) return null;
  let lt = m[1].split(/\s+/).filter(Boolean);
  while (lt.length) {
    const expr = `${lt.join(" ")} = ${rt.join(" ")}`;
    const solved = solveRoots(lt.join(" "), rt.join(" "));
    if (solved && solved.roots.length) return expr;
    lt = lt.slice(1);
  }
  return null;
}

// ---------------- Hinweis-Leiter (Port aus tutor.py) ----------------
const LOESUNG = "l(?:oe|ö|o)sung";
const ZIEL = `(?:${LOESUNG}|antwort|ergebnis|resultat)`;
const BETTEL = [
  `gib (mir )?die ${LOESUNG}`, `sag(s)? mir die ${LOESUNG}`, `was ist die ${LOESUNG}`,
  "einfach die antwort", "sag einfach", "verrat", `${LOESUNG} bitte`, "nur die antwort",
  "gib die antwort", "sag mir das ergebnis", `${LOESUNG}\\s*🙏`, "bitte die antwort",
  `zeig (mir )?(die|den|das)? ?${ZIEL}`, `nenn(e)? (mir )?(die|das)? ?${ZIEL}`,
  `wie (lautet|heisst|ist) (die|das) ${ZIEL}`, `sag (mir )?(die|das) ${ZIEL}`,
  `gib (mir )?(die|das) ${ZIEL}`, `was ist (die|das) ${ZIEL}`,
].map((p) => new RegExp(p));
const HILFE = [
  "weiss (es )?nicht", "keine ahnung", "komm(e)? nicht weiter", "h[aä]nge", "h[iä]lfe",
  "kapier", "versteh(e)? (es )?nicht", "tipp", "hinweis", "n[aä]chste stufe",
  "wie (geht|mach|anfangen|weiter)", "was (jetzt|nun|soll ich)", "stecke fest",
].map((p) => new RegExp(p));

function detectIntent(message, v) {
  const low = message.toLowerCase();
  if (v.status === "correct") return "correct";
  if (BETTEL.some((r) => r.test(low))) return "plea";
  if (v.status === "partial" || v.status === "incorrect") return "attempt";
  if (v.extracted) return "attempt";
  if (new RegExp(ZIEL).test(low)) return "plea"; // fragt nach Loesung ohne eigenen Versuch
  if (HILFE.some((r) => r.test(low))) return "stuck";
  return "stuck";
}

function advanceLadder(stage, attempts, intent, minAttempts = 2) {
  if (intent === "correct") return { stage: Math.max(stage, 1), attempts, solved: true, permit: false, intent };
  if (intent === "plea") return { stage: Math.max(stage, 1), attempts, solved: false, permit: false, intent };
  if (intent === "attempt") attempts += 1;
  let s = Math.min(Math.max(stage, 0) + 1, 4);
  const permit = s >= 4 && attempts >= minAttempts;
  if (s === 4 && !permit) s = 3;
  return { stage: s, attempts, solved: false, permit, intent };
}

function mockReply(step, v) {
  if (step.intent === "post_solved")
    return "Die hast du schon gelöst 🙂 Wenn du magst, erklär ich dir einen Schritt genauer – oder du startest eine neue Aufgabe.";
  if (step.intent === "correct")
    return "Stark, das stimmt! 🎉 Du hast sauber nach der Variablen aufgelöst. Mag noch eine Aufgabe?";
  if (step.intent === "plea")
    return "Mach ich extra nicht 🙂 – aber ich bring dich hin. Was fällt dir als Erstes auf, das du wegbekommen willst?";
  if (step.stage === 1)
    return "Kein Stress. Schau die Gleichung an: Was müsstest du zuerst tun, damit die Zahl auf derselben Seite wie das $x$ verschwindet?";
  if (step.stage === 2)
    return "Kleiner Tipp: Was auf der einen Seite passiert, machst du auch auf der anderen. Überleg, welche Gegen-Rechnung den Störer auffliegen lässt.";
  if (step.stage === 3)
    return "Ich mach den ersten Schritt vor: Bring die Zahl ohne $x$ mit der Gegenoperation auf die andere Seite. Was steht dann links, und was rechts? Rechne den nächsten Schritt selber.";
  const sol = v.solution || "die Lösung";
  return `Okay, jetzt gemeinsam bis zum Schluss: erst den Störer mit der Gegenoperation wegbringen, dann durch den Koeffizienten teilen. Damit kommst du auf ${sol}. Probier den letzten Schritt nochmal selbst nach.`;
}

// ---------------- Store-Helfer ----------------
function userByToken(headers) {
  const h = headers?.Authorization || headers?.authorization || "";
  const m = /^Bearer demo-(\d+)$/.exec(h);
  return m ? db.users.find((u) => u.id === Number(m[1])) : null;
}
function userOut(u) {
  return { id: u.id, email: u.email, display_name: u.display_name, role: u.role,
    grade_level: u.grade_level, language: u.language || "de", plan: "free",
    token_balance: 0, share_with_parents: u.share_with_parents !== false };
}
function topicOut(t, uid) {
  const exs = db.exercises.filter((e) => e.topic_id === t.id && e.user_id === uid);
  const solvedIds = new Set(db.attempts.filter((a) => a.solved).map((a) => a.exercise_id));
  const solved = exs.filter((e) => solvedIds.has(e.id)).length;
  const pct = exs.length ? Math.round((solved / exs.length) * 100) : 0;
  const label = !exs.length ? "Neu" : pct >= 90 ? "Sitzt" : pct >= 45 ? "Wird besser" : "Noch üben";
  return { ...t, exercise_count: exs.length, solved_count: solved, progress_pct: pct, progress_label: label };
}
function attemptOut(a) {
  return { id: a.id, exercise_id: a.exercise_id, status: a.solved ? "solved" : "active",
    hint_level: a.hint_level, own_attempts: a.own_attempts, solved: a.solved };
}
function exerciseOut(e) {
  return { id: e.id, text: e.text, math_expression: e.math_expression, topic_id: e.topic_id,
    image_path: e.image_path || null, created_at: e.created_at };
}
function stateOut(a) {
  const ex = db.exercises.find((e) => e.id === a.exercise_id);
  const msgs = db.messages.filter((m) => m.attempt_id === a.id);
  return { attempt: attemptOut(a), exercise: exerciseOut(ex),
    messages: msgs.map((m) => ({ id: m.id, role: m.role, text: m.text, created_at: m.created_at,
      verification_status: m.vstatus || null })) };
}
function summary(student) {
  const atts = db.attempts.filter((a) => a.user_id === student.id);
  const solved = atts.filter((a) => a.solved);
  const autonomous = solved.filter((a) => a.hint_level <= 2);
  const daily = [0, 0, 0, 0, 0, 0, 0];
  const days = new Set();
  for (const a of atts) {
    const d = new Date(a.created_at);
    const idx = (d.getDay() + 6) % 7; // Mo=0
    daily[idx]++; days.add(idx);
  }
  const topicName = (tid) => db.topics.find((t) => t.id === tid)?.name || "Thema";
  const struggles = {};
  for (const a of atts) {
    const ex = db.exercises.find((e) => e.id === a.exercise_id);
    if (ex?.topic_id && (!a.solved || a.hint_level >= 3))
      struggles[topicName(ex.topic_id)] = (struggles[topicName(ex.topic_id)] || 0) + 1;
  }
  return {
    student_display_name: student.display_name, grade_level: student.grade_level,
    autonomy_rate: solved.length ? Math.round((autonomous.length / solved.length) * 100) : 0,
    solved_count: solved.length, active_days: days.size,
    dranbleiben_delta: solved.length ? 100 : 0,
    top_struggles: Object.keys(struggles).slice(0, 3).map((t) => ({ topic: t, label: "Noch üben" })),
    daily_activity: daily, week_start: now().slice(0, 10),
    shared: student.share_with_parents !== false,
  };
}

// ---------------- Routen ----------------
const J = (data, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
const ERR = (detail, status) => J({ detail }, status);

const routes = [
  ["POST", /^\/api\/auth\/register$/, async (_, body) => {
    const email = (body.email || "").toLowerCase().trim();
    let u = db.users.find((x) => x.email === email);
    if (u && u.password) return ERR("Konto existiert bereits – wechsle zu «Anmelden».", 409);
    if (!u) {
      u = { id: nid(), email, display_name: (body.display_name || email.split("@")[0]).slice(0, 80),
        role: body.role === "parent" ? "parent" : "student",
        grade_level: body.grade_level || null, language: "de", share_with_parents: true };
      db.users.push(u);
    }
    u.password = body.password; save();
    return J({ access_token: `demo-${u.id}`, token_type: "bearer", user: userOut(u) });
  }],
  ["POST", /^\/api\/auth\/login$/, async (_, body) => {
    const email = (body.email || "").toLowerCase().trim();
    const u = db.users.find((x) => x.email === email);
    if (!u || !u.password || u.password !== body.password) return ERR("E-Mail oder Passwort falsch.", 401);
    return J({ access_token: `demo-${u.id}`, token_type: "bearer", user: userOut(u) });
  }],
  ["POST", /^\/api\/auth\/request-link$/, async (_, body) => {
    const email = (body.email || "").toLowerCase().trim();
    let u = db.users.find((x) => x.email === email);
    if (!u) {
      if (!body.register) return ERR("Kein Konto mit dieser E-Mail – wechsle zu «Neu hier».", 404);
      u = { id: nid(), email, display_name: (body.display_name || email.split("@")[0]).slice(0, 80),
        role: body.role === "parent" ? "parent" : "student",
        grade_level: body.grade_level || null, language: "de", share_with_parents: true };
      db.users.push(u);
    }
    const token = `m${nid()}`;
    db.magic[token] = u.id; save();
    return J({ sent: false, message: "Demo-Modus", dev_login_url: `#/login/verify?token=${token}`, dev_token: token });
  }],
  ["POST", /^\/api\/auth\/verify$/, async (_, body) => {
    const uid = db.magic[body.token];
    if (!uid) return ERR("Link ungültig oder bereits benutzt.", 400);
    delete db.magic[body.token]; save();
    const u = db.users.find((x) => x.id === uid);
    return J({ access_token: `demo-${u.id}`, token_type: "bearer", user: userOut(u) });
  }],
  ["GET", /^\/api\/auth\/me$/, async (m, _, u) => u ? J(userOut(u)) : ERR("Nicht angemeldet", 401)],
  ["PATCH", /^\/api\/auth\/me$/, async (_, body, u) => {
    if (!u) return ERR("Nicht angemeldet", 401);
    for (const k of ["display_name", "grade_level", "language", "share_with_parents"])
      if (body[k] !== undefined) u[k] = body[k];
    save(); return J(userOut(u));
  }],

  ["GET", /^\/api\/topics$/, async (_, __, u) =>
    u?.role === "student" ? J(db.topics.filter((t) => t.user_id === u.id).map((t) => topicOut(t, u.id))) : ERR("Nur für Schüler-Konten", 403)],
  ["POST", /^\/api\/topics$/, async (_, body, u) => {
    if (u?.role !== "student") return ERR("Nur für Schüler-Konten", 403);
    const t = { id: nid(), user_id: u.id, name: body.name, category: body.category || "andere",
      color: body.color || "#6366f1", created_at: now() };
    db.topics.push(t); save(); return J(topicOut(t, u.id), 201);
  }],
  ["PATCH", /^\/api\/topics\/(\d+)$/, async (m, body, u) => {
    const t = db.topics.find((x) => x.id === Number(m[1]) && x.user_id === u?.id);
    if (!t) return ERR("Thema nicht gefunden", 404);
    Object.assign(t, body); save(); return J(topicOut(t, u.id));
  }],
  ["DELETE", /^\/api\/topics\/(\d+)$/, async (m, _, u) => {
    const i = db.topics.findIndex((x) => x.id === Number(m[1]) && x.user_id === u?.id);
    if (i < 0) return ERR("Thema nicht gefunden", 404);
    db.exercises.forEach((e) => { if (e.topic_id === db.topics[i].id) e.topic_id = null; });
    db.topics.splice(i, 1); save(); return new Response(null, { status: 204 });
  }],
  ["GET", /^\/api\/topics\/(\d+)\/exercises$/, async (m, _, u) => {
    const t = db.topics.find((x) => x.id === Number(m[1]) && x.user_id === u?.id);
    if (!t) return ERR("Thema nicht gefunden", 404);
    const items = db.exercises.filter((e) => e.topic_id === t.id).map((e) => {
      const last = [...db.attempts].reverse().find((a) => a.exercise_id === e.id);
      return { id: e.id, text: e.text, math_expression: e.math_expression, created_at: e.created_at,
        latest_attempt_id: last?.id || null, solved: !!last?.solved };
    });
    return J(items.reverse());
  }],

  ["POST", /^\/api\/exercises$/, async (_, body, u) => {
    if (u?.role !== "student") return ERR("Nur für Schüler-Konten", 403);
    const txt = (body.text || "").trim();
    const e = { id: nid(), user_id: u.id, text: txt,
      math_expression: (body.math_expression || "").trim() || extractExpression(txt),
      topic_id: body.topic_id || null, image_path: body.image_path || null, created_at: now() };
    db.exercises.push(e); save(); return J(exerciseOut(e), 201);
  }],
  ["POST", /^\/api\/exercises\/(\d+)\/attempts$/, async (m, _, u) => {
    const ex = db.exercises.find((x) => x.id === Number(m[1]) && x.user_id === u?.id);
    if (!ex) return ERR("Aufgabe nicht gefunden", 404);
    const a = { id: nid(), exercise_id: ex.id, user_id: u.id, hint_level: 0, own_attempts: 0,
      solved: false, created_at: now() };
    db.attempts.push(a);
    db.messages.push({ id: nid(), attempt_id: a.id, role: "tutor", created_at: now(),
      text: `Los geht's! Deine Aufgabe:\n\n${ex.text}\n\nWie würdest du anfangen? Kein Stress – ich helf dir Schritt für Schritt.` });
    save(); return J(stateOut(a), 201);
  }],
  ["POST", /^\/api\/exercises\/ocr$/, async () =>
    J({ text: "", math_expression: null, confidence: 0,
        image_path: null })],

  ["GET", /^\/api\/attempts\/(\d+)$/, async (m, _, u) => {
    if (u?.role !== "student") return ERR("Nur für Schüler-Konten", 403);
    const a = db.attempts.find((x) => x.id === Number(m[1]) && x.user_id === u.id);
    return a ? J(stateOut(a)) : ERR("Session nicht gefunden", 404);
  }],
  ["POST", /^\/api\/attempts\/(\d+)\/chat$/, async (m, body, u) => {
    const a = db.attempts.find((x) => x.id === Number(m[1]) && x.user_id === u?.id);
    if (!a) return ERR("Session nicht gefunden", 404);
    const ex = db.exercises.find((e) => e.id === a.exercise_id);
    const text = (body.text || "").trim();
    const v = verify(ex.math_expression, text);
    let step;
    if (a.solved) {
      step = { stage: Math.max(a.hint_level, 1), attempts: a.own_attempts, solved: true,
        intent: v.status === "correct" ? "correct" : "post_solved" };
    } else {
      const intent = detectIntent(text, v);
      step = advanceLadder(a.hint_level, a.own_attempts, intent);
      a.hint_level = step.stage; a.own_attempts = step.attempts;
      if (step.solved) a.solved = true;
    }
    db.messages.push({ id: nid(), attempt_id: a.id, role: "student", text, created_at: now(), vstatus: v.status });
    const reply = mockReply(step, v);
    db.messages.push({ id: nid(), attempt_id: a.id, role: "tutor", text: reply, created_at: now() });
    save();
    // Streaming nachbilden: Wort für Wort
    const words = reply.match(/\S+\s*/g) || [reply];
    const enc = new TextEncoder();
    const stream = new ReadableStream({
      async start(ctrl) {
        for (const w of words) {
          ctrl.enqueue(enc.encode(w));
          await new Promise((r) => setTimeout(r, 24));
        }
        ctrl.close();
      },
    });
    return new Response(stream, { status: 200, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }],

  ["GET", /^\/api\/quota$/, async (_, __, u) => {
    if (u?.role !== "student") return ERR("Nur für Schüler-Konten", 403);
    const used = db.exercises.filter((e) => e.user_id === u.id).length;
    return J({ plan: "free", used_this_month: used, monthly_free_quota: 5, token_balance: 0,
      remaining: Math.max(20 - used, 0), percent_used: Math.min(Math.round((used / 20) * 100), 100) });
  }],

  ["GET", /^\/api\/parents\/invite$/, async (_, __, u) => {
    if (u?.role !== "student") return ERR("Nur für Schüler-Konten", 403);
    let link = db.links.find((l) => l.student_id === u.id && l.status === "pending");
    if (!link) {
      link = { code: Math.random().toString(36).slice(2, 10).toUpperCase(), student_id: u.id,
        parent_id: null, status: "pending" };
      db.links.push(link); save();
    }
    return J({ invite_code: link.code, status: link.status });
  }],
  ["GET", /^\/api\/parents\/preview$/, async (_, __, u) =>
    u?.role === "student" ? J(summary(u)) : ERR("Nur für Schüler-Konten", 403)],
  ["POST", /^\/api\/parents\/redeem$/, async (_, body, u) => {
    if (u?.role !== "parent") return ERR("Nur für Eltern-Konten", 403);
    const code = (body.invite_code || "").trim().toUpperCase();
    const link = db.links.find((l) => l.code === code);
    if (!link) return ERR("Code nicht gefunden.", 404);
    if (link.status === "linked" && link.parent_id !== u.id)
      return ERR("Code wurde bereits verwendet – lass dir einen neuen geben.", 400);
    if (link.status !== "linked") { link.parent_id = u.id; link.status = "linked"; save(); }
    return J(summary(db.users.find((x) => x.id === link.student_id)));
  }],
  ["GET", /^\/api\/parents\/children$/, async (_, __, u) => {
    if (u?.role !== "parent") return ERR("Nur für Eltern-Konten", 403);
    return J(db.links.filter((l) => l.parent_id === u.id && l.status === "linked")
      .map((l) => summary(db.users.find((x) => x.id === l.student_id))));
  }],
];

// ---------------- fetch-Interceptor ----------------
const realFetch = window.fetch.bind(window);
window.fetch = async (input, init = {}) => {
  const url = typeof input === "string" ? input : input.url;
  const path = url.replace(/^https?:\/\/[^/]+/, "").split("?")[0];
  if (!path.startsWith("/api/")) return realFetch(input, init);
  const method = (init.method || "GET").toUpperCase();
  let body = {};
  if (init.body && !(init.body instanceof FormData)) {
    try { body = JSON.parse(init.body); } catch { body = {}; }
  }
  const user = userByToken(init.headers || {});
  for (const [m, re, handler] of routes) {
    const match = m === method && re.exec(path);
    if (match) {
      await new Promise((r) => setTimeout(r, 120)); // kleine Netz-Latenz simulieren
      try { return await handler(match, body, user); }
      catch (e) { return ERR(`Demo-Fehler: ${e.message}`, 500); }
    }
  }
  return ERR("Not Found", 404);
};

// ---------------- Demo-Hinweisband ----------------
const ribbon = document.createElement("div");
ribbon.innerHTML = "🧪 <b>Demo-Modus</b> – läuft ohne Server: Daten bleiben in diesem Browser, der Tutor ist der Übungs-Mock (ohne echte KI).";
ribbon.style.cssText =
  "position:fixed;bottom:10px;left:50%;transform:translateX(-50%);z-index:9999;" +
  "background:#1a1c22;color:#e7e8ee;font:12px/1.45 Inter,system-ui,sans-serif;" +
  "padding:8px 14px;border-radius:999px;box-shadow:0 8px 30px rgba(20,20,50,.35);" +
  "max-width:92vw;text-align:center;pointer-events:auto;cursor:pointer;";
ribbon.title = "Klicken zum Ausblenden";
ribbon.onclick = () => ribbon.remove();
document.addEventListener("DOMContentLoaded", () => document.body.appendChild(ribbon));
if (document.readyState !== "loading") document.body.appendChild(ribbon);

console.info("[Schrittweise] Demo-Modus aktiv – /api/* wird im Browser simuliert.");
