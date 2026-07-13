import { useEffect, useState, useCallback, createContext, useContext } from "react";
import { Outlet, useNavigate, useLocation, Link } from "react-router-dom";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";
import NewTaskModal from "./NewTaskModal.jsx";
import FeedbackModal from "./FeedbackModal.jsx";

const ShellCtx = createContext(null);
export function useShell() {
  return useContext(ShellCtx);
}

const CATEGORY_DOT = {
  algebra: "#6366f1",
  geometrie: "#e0993a",
  zahlen: "#1a7f3c",
  andere: "#9aa0ab",
};

export default function AppShell() {
  const nav = useNavigate();
  const loc = useLocation();
  const { user, logout } = useAuth();
  const [topics, setTopics] = useState([]);
  const [quota, setQuota] = useState(null);
  const [modal, setModal] = useState(null); // null | {topicId?}
  const [fbOpen, setFbOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [updateReady, setUpdateReady] = useState(false);
  const [mailOk, setMailOk] = useState(false);
  const [verifyNote, setVerifyNote] = useState(null); // null | "ok" | "fehler"

  // Kann der Server Mails verschicken? Nur dann macht der Bestätigungs-Banner Sinn.
  useEffect(() => {
    api.get("/api/health").then((h) => setMailOk(!!h?.mail)).catch(() => setMailOk(false));
  }, []);

  const sendVerifyMail = async () => {
    try {
      await api.post("/api/auth/request-link", { email: user.email });
      setVerifyNote("ok");
    } catch {
      setVerifyNote("fehler");
    }
  };

  // Update-Erkennung: alte, lange offene Tabs zeigten sonst ein veraltetes
  // Bundle (kaputte Skizzen/Formatierung). Beim Zurueckkehren in den Tab und
  // alle 15 Min wird das aktuelle index.html geholt und der Bundle-Name mit
  // dem geladenen Script verglichen – weicht er ab, erscheint der Reload-Knopf.
  useEffect(() => {
    const current = document.querySelector('script[src*="/assets/index-"]')?.getAttribute("src");
    if (!current) return; // Dev-Server: kein gebautes Bundle
    let stop = false;
    const check = async () => {
      try {
        const res = await fetch("/", { cache: "no-store" });
        const m = (await res.text()).match(/\/assets\/index-[^"]+\.js/);
        if (!stop && m && m[0] !== current) setUpdateReady(true);
      } catch { /* offline o.ae. – beim naechsten Check erneut versuchen */ }
    };
    const onVis = () => {
      if (document.visibilityState === "visible") check();
    };
    document.addEventListener("visibilitychange", onVis);
    const id = setInterval(check, 15 * 60 * 1000);
    check();
    return () => {
      stop = true;
      clearInterval(id);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []);

  const loadTopics = useCallback(async () => {
    try {
      setTopics(await api.get("/api/topics"));
    } catch {
      setTopics([]);
    }
  }, []);

  const loadQuota = useCallback(async () => {
    try {
      setQuota(await api.get("/api/quota"));
    } catch {
      setQuota(null);
    }
  }, []);

  useEffect(() => {
    loadTopics();
    loadQuota();
  }, [loadTopics, loadQuota]);

  // Mobile-Navigation bei Seitenwechsel schliessen
  useEffect(() => {
    setNavOpen(false);
  }, [loc.pathname]);

  const isActive = (path) => loc.pathname.startsWith(`/app/${path}`);
  const initial = (user?.display_name || "?").charAt(0).toUpperCase();
  const quotaPct = quota ? quota.percent_used : 0;

  const navItem = (active) => ({
    display: "flex",
    alignItems: "center",
    gap: 10,
    margin: "2px 8px",
    padding: "9px 12px",
    borderRadius: 10,
    fontSize: 13,
    cursor: "pointer",
    background: active ? "#eef0fe" : "transparent",
    color: active ? "#4f46e5" : "#1a1c22",
    fontWeight: active ? 600 : 400,
  });

  const shellValue = {
    topics,
    reloadTopics: loadTopics,
    reloadQuota: loadQuota,
    openNewTask: (topicId) => setModal({ topicId: typeof topicId === "number" ? topicId : undefined }),
    quota,
  };

  return (
    <ShellCtx.Provider value={shellValue}>
      <div style={{ height: "100vh", display: "flex", background: "#fff", overflow: "hidden" }} className="app-root">
        <div className={`sidebar-backdrop ${navOpen ? "show" : ""}`} onClick={() => setNavOpen(false)} />
        {/* SIDEBAR */}
        <div style={{ flex: "0 0 244px", background: "#fbfbfd", borderRight: "1px solid #eef0f3", display: "flex", flexDirection: "column" }} className={`sidebar ${navOpen ? "open" : ""}`}>
          <Link to="/" style={{ display: "flex", alignItems: "center", gap: 9, padding: "16px 16px 12px" }}>
            <span style={{ width: 22, height: 22, borderRadius: 7, background: "#6366f1" }} />
            <span style={{ fontWeight: 800, fontSize: 16, color: "#4f46e5", letterSpacing: "-.02em" }}>Schrittweise</span>
          </Link>

          <button
            onClick={() => setModal({})}
            className="btn-primary"
            style={{ margin: "2px 12px 14px", display: "flex", alignItems: "center", justifyContent: "center", gap: 6, fontSize: 13, borderRadius: 11, padding: 11 }}
          >
            + Neue Aufgabe
          </button>

          <div onClick={() => nav("/app/themen")} style={navItem(isActive("themen"))}>▦ Themen</div>

          <div style={{ padding: "8px 16px 4px", fontSize: 11, fontWeight: 700, letterSpacing: ".1em", color: "#9aa0ab" }}>LERNEN</div>
          <div style={{ overflowY: "auto", flex: "0 1 auto" }}>
            {topics.length === 0 && (
              <div style={{ padding: "6px 20px", fontSize: 12, color: "#b6bcc6" }}>Noch keine Themen – leg eins an ✦</div>
            )}
            {topics.map((t) => {
              const active = loc.pathname === `/app/themen/${t.id}` || loc.search.includes(`topic=${t.id}`);
              return (
                <div key={t.id} onClick={() => nav(`/app/themen/${t.id}`)} style={{ ...navItem(active), margin: "0 8px" }}>
                  <span style={{ width: 7, height: 7, borderRadius: "50%", background: t.color || CATEGORY_DOT[t.category] || "#9aa0ab" }} />
                  {t.name}
                </div>
              );
            })}
          </div>

          <div style={{ padding: "12px 16px 4px", fontSize: 11, fontWeight: 700, letterSpacing: ".1em", color: "#9aa0ab" }}>MEHR</div>
          <div onClick={() => nav("/app/bibliothek")} style={{ ...navItem(isActive("bibliothek")), margin: "0 8px" }}>📚 Bibliothek</div>
          <div onClick={() => nav("/app/eltern")} style={{ ...navItem(isActive("eltern")), margin: "0 8px" }}>👪 Eltern verbinden</div>
          <div onClick={() => setFbOpen(true)} style={{ ...navItem(false), margin: "0 8px" }}>💬 Feedback</div>
          {user?.is_admin && (
            <>
              <div onClick={() => nav("/app/kosten")} style={{ ...navItem(isActive("kosten")), margin: "0 8px" }}>📊 Kosten</div>
              <div onClick={() => nav("/app/nutzer")} style={{ ...navItem(isActive("nutzer")), margin: "0 8px" }}>👥 Nutzer</div>
            </>
          )}

          <div style={{ marginTop: "auto", borderTop: "1px solid #eef0f3", padding: "12px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
            <div onClick={() => nav("/app/einstellungen")} style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
              <span style={{ width: 28, height: 28, borderRadius: "50%", background: "#eef0fe", color: "#4f46e5", fontWeight: 700, fontSize: 13, display: "grid", placeItems: "center" }}>{initial}</span>
              <div style={{ lineHeight: 1.2 }}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{user?.display_name}</div>
                <div style={{ fontSize: 11, color: "#9aa0ab" }}>{user?.grade_level || "Oberstufe"}</div>
              </div>
              <span style={{ marginLeft: "auto", color: "#9aa0ab", fontSize: 15 }}>⚙</span>
            </div>
            {quota?.unlimited ? (
              <div style={{ fontSize: 10, color: "#9aa0ab" }}>∞ Unbegrenzte Aufgaben (Betreiber)</div>
            ) : (
              <div onClick={() => nav("/app/preise")} style={{ cursor: "pointer" }}>
                <div style={{ fontSize: 10, color: "#9aa0ab", marginBottom: 4 }}>
                  {quota ? `⚡ ${quota.remaining} Tokens übrig` : "Tokens · …"}
                </div>
                <div style={{ height: 5, borderRadius: 999, background: "#e7e8ee", overflow: "hidden" }}>
                  <div style={{ width: `${quotaPct}%`, height: "100%", background: quotaPct >= 90 ? "#d9573a" : "#cdd2db" }} />
                </div>
              </div>
            )}
            <div onClick={logout} style={{ fontSize: 11, color: "#b6bcc6", cursor: "pointer" }}>Abmelden</div>
          </div>
        </div>

        {/* MAIN */}
        <div style={{ flex: 1, minWidth: 0, position: "relative", display: "flex", flexDirection: "column" }}>
          <div className="mobile-topbar">
            <button onClick={() => setNavOpen(true)} aria-label="Menü" style={{ width: 36, height: 36, borderRadius: 10, border: "1px solid #e7e8ee", background: "#fff", fontSize: 16 }}>☰</button>
            <span style={{ width: 20, height: 20, borderRadius: 6, background: "#6366f1" }} />
            <span style={{ fontWeight: 800, fontSize: 15, color: "#4f46e5", letterSpacing: "-.02em" }}>Schrittweise</span>
            <button onClick={() => setModal({})} className="btn-primary" style={{ marginLeft: "auto", fontSize: 12, borderRadius: 9, padding: "8px 12px", border: "none" }}>+ Aufgabe</button>
          </div>
          {user?.email_verified === false && mailOk && (
            <div style={{ background: "#fdf3e6", borderBottom: "1px solid #f2ddb8", padding: "8px 16px", fontSize: 12.5, color: "#a05c12", display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <span>📧 Bestätige deine E-Mail – klick auf den Link, den wir dir geschickt haben. So kannst du dein Passwort jederzeit wiederherstellen.</span>
              <button
                onClick={sendVerifyMail}
                disabled={verifyNote === "ok"}
                style={{ border: "1px solid #e3c795", background: "#fff", color: "#a05c12", borderRadius: 999, padding: "4px 12px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}
              >
                {verifyNote === "ok" ? "Link geschickt ✓" : verifyNote === "fehler" ? "Nochmal versuchen" : "Link nochmal senden"}
              </button>
            </div>
          )}
          <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
            <Outlet />
          </div>
        </div>

        {modal && <NewTaskModal presetTopicId={modal.topicId} onClose={() => setModal(null)} />}
        {fbOpen && <FeedbackModal onClose={() => setFbOpen(false)} />}
        {updateReady && (
          <div style={{ position: "fixed", bottom: 18, left: "50%", transform: "translateX(-50%)", zIndex: 300, background: "#1a1c22", color: "#fff", borderRadius: 999, padding: "9px 10px 9px 18px", display: "flex", gap: 14, alignItems: "center", boxShadow: "0 10px 30px rgba(0,0,0,.28)", fontSize: 13, whiteSpace: "nowrap" }}>
            ✨ Neue Version verfügbar
            <button
              onClick={() => window.location.reload()}
              style={{ background: "#6366f1", color: "#fff", border: "none", borderRadius: 999, padding: "8px 16px", fontSize: 13, fontWeight: 700, cursor: "pointer" }}
            >
              Jetzt aktualisieren
            </button>
          </div>
        )}
      </div>
    </ShellCtx.Provider>
  );
}
