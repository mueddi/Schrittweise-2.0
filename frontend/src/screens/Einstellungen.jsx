import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";

const TABS = [
  { key: "profil", icon: "👤", label: "Profil" },
  { key: "passwort", icon: "🔑", label: "Passwort" },
  { key: "sprache", icon: "🌐", label: "Sprache" },
  { key: "privat", icon: "🔒", label: "Privatsphäre" },
  { key: "abo", icon: "💳", label: "Abo & Tokens" },
];
const GRADES = ["1. Oberstufe", "2. Oberstufe", "3. Oberstufe"];

export default function Einstellungen() {
  const nav = useNavigate();
  const { user, setUser } = useAuth();
  const [tab, setTab] = useState("profil");
  const [name, setName] = useState(user?.display_name || "");
  const [grade, setGrade] = useState(user?.grade_level || "2. Oberstufe");
  const [language, setLanguage] = useState(user?.language || "de");
  const [share, setShare] = useState(user?.share_with_parents ?? true);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  async function save(extra = {}) {
    setBusy(true);
    setSaved(false);
    try {
      const updated = await api.patch("/api/auth/me", {
        display_name: name,
        grade_level: grade,
        language,
        share_with_parents: share,
        ...extra,
      });
      setUser(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      return true;
    } catch (e) {
      alert(e.message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  const initial = (user?.display_name || "?").charAt(0).toUpperCase();

  return (
    <div style={{ height: "100%", display: "flex" }} className="settings">
      <div style={{ flex: "0 0 220px", background: "#fbfbfd", borderRight: "1px solid #eef0f3", padding: "18px 0" }} className="settings-nav">
        <div style={{ padding: "0 18px 14px", fontSize: 18, fontWeight: 800, letterSpacing: "-.02em" }}>Einstellungen</div>
        {TABS.map((t) => (
          <div
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{ display: "flex", alignItems: "center", gap: 10, margin: "2px 8px", padding: "9px 12px", borderRadius: 10, fontSize: 13, cursor: "pointer", background: tab === t.key ? "#eef0fe" : "transparent", color: tab === t.key ? "#4f46e5" : "#1a1c22", fontWeight: tab === t.key ? 600 : 400 }}
          >
            {t.icon} {t.label}
          </div>
        ))}
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "30px 36px", background: "#fff" }}>
        {tab === "profil" && (
          <>
            <div style={{ fontSize: 20, fontWeight: 800, letterSpacing: "-.02em", marginBottom: 24 }}>Profil</div>
            <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 28 }}>
              <span style={{ width: 64, height: 64, borderRadius: "50%", background: "#eef0fe", color: "#4f46e5", fontWeight: 800, fontSize: 24, display: "grid", placeItems: "center" }}>{initial}</span>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#4f46e5", marginBottom: 4 }}>Anzeigename statt Klarname</div>
                <div style={{ fontSize: 12, color: "#9aa0ab" }}>Wir speichern bewusst keinen echten Namen.</div>
              </div>
            </div>
            <div style={{ maxWidth: 520 }}>
              <Field label="Anzeigename">
                <input value={name} onChange={(e) => setName(e.target.value)} className="input-clean" style={{ width: "100%", fontSize: 14 }} />
              </Field>
              <Field label="E-Mail">
                <div style={{ display: "flex", justifyContent: "space-between", color: "#6b7280" }}>
                  <span>{user?.email}</span>
                  {user?.email_verified ? (
                    <span style={{ fontSize: 11, color: "#1a7f3c", fontWeight: 700 }}>✓ bestätigt</span>
                  ) : (
                    <span style={{ fontSize: 11, color: "#a05c12", fontWeight: 700 }}>noch nicht bestätigt</span>
                  )}
                </div>
              </Field>
              <Field label="Klassenstufe">
                <select value={grade} onChange={(e) => setGrade(e.target.value)} style={selectStyle}>
                  {GRADES.map((g) => <option key={g}>{g}</option>)}
                </select>
              </Field>
              <SaveRow busy={busy} saved={saved} onSave={() => save()} onCancel={() => nav("/app/lernen")} />
            </div>
          </>
        )}

        {tab === "passwort" && <PasswordTab />}

        {tab === "abo" && <AboTab onBuy={() => nav("/app/preise")} />}

        {tab === "sprache" && (
          <>
            <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 24 }}>Sprache</div>
            <div style={{ maxWidth: 520 }}>
              <Field label="Sprache der App">
                <select value={language} onChange={(e) => setLanguage(e.target.value)} style={selectStyle}>
                  <option value="de">Deutsch (Schweiz)</option>
                  <option value="fr">Français</option>
                  <option value="it">Italiano</option>
                </select>
              </Field>
              <div style={{ fontSize: 12, color: "#9aa0ab", marginBottom: 20 }}>Weitere Sprachen folgen. Der Tutor bleibt vorerst auf Deutsch.</div>
              <SaveRow busy={busy} saved={saved} onSave={() => save()} onCancel={() => nav("/app/lernen")} />
            </div>
          </>
        )}

        {tab === "privat" && (
          <>
            <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 24 }}>Privatsphäre</div>
            <div style={{ maxWidth: 620 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", borderTop: "1px solid #eef0f3", padding: "16px 0" }}>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>Fortschritt für Eltern freigeben</div>
                  <div style={{ fontSize: 12, color: "#9aa0ab" }}>Nur grober Fortschritt, keine einzelnen Nachrichten.</div>
                </div>
                <Toggle on={share} onClick={async () => {
                  const next = !share;
                  setShare(next);
                  const ok = await save({ share_with_parents: next });
                  if (!ok) setShare(!next); // PATCH fehlgeschlagen -> Schalter zuruecksetzen
                }} />
              </div>
              <div style={{ background: "#f6f7fb", border: "1px solid #eef0f3", borderRadius: 14, padding: 16, fontSize: 13, color: "#6b7280", lineHeight: 1.55, marginTop: 12 }}>
                🔒 Deine Chats bleiben privat. Eltern sehen nur Aggregate wie Selbständigkeit, gelöste Aufgaben und Themen-Trends – technisch gibt es aus der Eltern-Ansicht keinen Zugriff auf deine Nachrichten.
              </div>
              <DeleteAccount />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function AboTab({ onBuy }) {
  const [quota, setQuota] = useState(null);
  useEffect(() => {
    api.get("/api/quota").then(setQuota).catch(() => setQuota(null));
  }, []);

  if (!quota) return <div style={{ fontSize: 14, color: "#9aa0ab" }}>lädt …</div>;

  if (quota.unlimited) {
    return (
      <>
        <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 24 }}>Abo &amp; Tokens</div>
        <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 14, padding: 20, maxWidth: 620 }}>
          <div style={{ fontSize: 12, color: "#9aa0ab", marginBottom: 6 }}>Plan</div>
          <div style={{ fontSize: 20, fontWeight: 800 }}>∞ Unbegrenzt</div>
          <div style={{ fontSize: 13, color: "#6b7280", marginTop: 8, lineHeight: 1.55 }}>
            Dieses Konto ist ein Betreiber-Konto: Aufgaben sind unbegrenzt und kostenlos –
            es werden weder Gratis-Kontingent noch Tokens abgebucht.
          </div>
        </div>
      </>
    );
  }

  const freeUsed = Math.min(quota.free_used_tokens, quota.monthly_free_tokens);
  const freePct = quota.monthly_free_tokens ? Math.min(100, Math.round((freeUsed / quota.monthly_free_tokens) * 100)) : 0;

  return (
    <>
      <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 24 }}>Abo &amp; Tokens</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14, maxWidth: 620, marginBottom: 20 }} className="eltern-tiles">
        <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 14, padding: 16 }}>
          <div style={{ fontSize: 12, color: "#9aa0ab", marginBottom: 6 }}>Plan</div>
          <div style={{ fontSize: 20, fontWeight: 800 }}>{quota.plan === "free" ? "Gratis" : "Token"}</div>
        </div>
        <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 14, padding: 16 }}>
          <div style={{ fontSize: 12, color: "#9aa0ab", marginBottom: 6 }}>Gratis-Tokens (Monat)</div>
          <div style={{ fontSize: 20, fontWeight: 800 }}>{freeUsed} <span style={{ fontSize: 13, color: "#9aa0ab" }}>von {quota.monthly_free_tokens}</span></div>
          <div style={{ height: 5, borderRadius: 999, background: "#eef0f3", overflow: "hidden", marginTop: 8 }}>
            <div style={{ width: `${freePct}%`, height: "100%", background: freePct >= 90 ? "#d9573a" : "#6366f1" }} />
          </div>
        </div>
        <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 14, padding: 16 }}>
          <div style={{ fontSize: 12, color: "#9aa0ab", marginBottom: 6 }}>Token-Guthaben</div>
          <div style={{ fontSize: 20, fontWeight: 800, color: quota.token_balance > 0 ? "#1a7f3c" : "#1a1c22" }}>{quota.token_balance}</div>
        </div>
      </div>
      <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 18, lineHeight: 1.55 }}>
        1 Token = 1 Rappen KI-Hilfe · eine normale Tutor-Antwort kostet ≈ 1 Token, eine Antwort mit
        Foto-Auswertung ≈ 3–5 · Tokens laufen nie ab · kein Abo, keine automatische Verlängerung
      </div>
      <button onClick={onBuy} className="btn-primary" style={{ padding: "11px 20px", borderRadius: 11, fontSize: 14, border: "none" }}>
        Tokens kaufen →
      </button>
    </>
  );
}

export function PasswordTab() {
  const { login } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(null); // {type, text}

  async function change() {
    if (next.length < 8) {
      setNote({ type: "error", text: "Das neue Passwort braucht mindestens 8 Zeichen." });
      return;
    }
    if (next !== repeat) {
      setNote({ type: "error", text: "Die beiden neuen Passwörter stimmen nicht überein." });
      return;
    }
    setBusy(true);
    setNote(null);
    try {
      const res = await api.post("/api/auth/change-password", {
        current_password: current || null,
        new_password: next,
      });
      await login(res.access_token, res.user); // frisches Token übernehmen
      setCurrent(""); setNext(""); setRepeat("");
      setNote({ type: "ok", text: "✓ Passwort geändert." });
    } catch (e) {
      setNote({ type: "error", text: e.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 8 }}>Passwort ändern</div>
      <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 24, maxWidth: 520 }}>
        Passwort vergessen? Melde dich ab und nutze auf der Anmelde-Seite «Passwort vergessen» –
        dann kommst du per E-Mail-Link zurück und kannst hier ohne altes Passwort ein neues setzen.
      </div>
      <div style={{ maxWidth: 520 }}>
        <Field label="Aktuelles Passwort">
          <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" className="input-clean" style={{ width: "100%", fontSize: 14 }} />
        </Field>
        <Field label="Neues Passwort (mind. 8 Zeichen)">
          <input type="password" value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" className="input-clean" style={{ width: "100%", fontSize: 14 }} />
        </Field>
        <Field label="Neues Passwort wiederholen">
          <input type="password" value={repeat} onChange={(e) => setRepeat(e.target.value)} autoComplete="new-password" className="input-clean" style={{ width: "100%", fontSize: 14 }} />
        </Field>
        {note && (
          <div style={{ fontSize: 13, marginBottom: 12, color: note.type === "error" ? "#c0392b" : "#1a7f3c", fontWeight: 600 }}>{note.text}</div>
        )}
        <button onClick={change} disabled={busy} className="btn-primary" style={{ padding: "11px 20px", borderRadius: 11, fontSize: 14, border: "none", opacity: busy ? 0.7 : 1 }}>
          {busy ? "ändert …" : "Passwort ändern"}
        </button>
      </div>
    </>
  );
}

const selectStyle = { width: "100%", border: "none", outline: "none", background: "transparent", fontSize: 14 };

function Field({ label, children }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <label style={{ fontSize: 12, fontWeight: 600, color: "#6b7280", display: "block", marginBottom: 6 }}>{label}</label>
      <div style={{ border: "1px solid #d2d4dd", borderRadius: 11, padding: "11px 13px", fontSize: 14 }}>{children}</div>
    </div>
  );
}

function SaveRow({ busy, saved, onSave, onCancel }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 18 }}>
      <button onClick={onSave} disabled={busy} className="btn-primary" style={{ padding: "11px 20px", borderRadius: 11, fontSize: 14, border: "none" }}>
        {busy ? "speichert …" : "Speichern"}
      </button>
      <button onClick={onCancel} className="btn-ghost" style={{ padding: "11px 20px", fontSize: 14 }}>Abbrechen</button>
      {saved && <span style={{ fontSize: 13, color: "#1a7f3c", fontWeight: 600 }}>✓ gespeichert</span>}
    </div>
  );
}

function Toggle({ on, onClick }) {
  return (
    <div onClick={onClick} style={{ width: 42, height: 24, borderRadius: 999, position: "relative", cursor: "pointer", background: on ? "#6366f1" : "#d2d4dd", transition: "background .15s" }}>
      <span style={{ position: "absolute", top: 2, left: on ? 20 : 2, width: 20, height: 20, borderRadius: "50%", background: "#fff", transition: "left .15s" }} />
    </div>
  );
}

// Roter Bereich: Konto endgültig löschen (Datenschutz-Selbstbedienung)
export function DeleteAccount() {
  const { logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function doDelete() {
    if (!window.confirm("Wirklich alles löschen? Aufgaben, Chats und Guthaben sind danach unwiderruflich weg.")) return;
    setBusy(true);
    setErr("");
    try {
      await api.post("/api/auth/delete-account", { password: pw });
      logout();
      window.location.href = "/";
    } catch (e) {
      setErr(e.message || "Löschen fehlgeschlagen.");
      setBusy(false);
    }
  }

  return (
    <div style={{ border: "1px solid #f2c9c0", background: "#fdf6f4", borderRadius: 14, padding: 16, marginTop: 24 }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: "#b3492f", marginBottom: 4 }}>Konto löschen</div>
      <div style={{ fontSize: 12.5, color: "#6b7280", lineHeight: 1.55, marginBottom: 12 }}>
        Löscht dein Konto mit allen Aufgaben, Chats, Bildern und deinem Token-Guthaben – endgültig.
        Zahlungsbelege bleiben beim Zahlungsanbieter (gesetzliche Aufbewahrung).
      </div>
      {!open ? (
        <button onClick={() => setOpen(true)} style={{ border: "1px solid #e5b0a4", background: "#fff", color: "#b3492f", borderRadius: 10, padding: "9px 14px", fontSize: 13, fontWeight: 700, cursor: "pointer" }}>
          Konto löschen …
        </button>
      ) : (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <input
            type="password"
            value={pw}
            onChange={(e) => setPw(e.target.value)}
            placeholder="Passwort zur Bestätigung"
            style={{ border: "1px solid #e5b0a4", borderRadius: 10, padding: "9px 12px", fontSize: 13, flex: "1 1 200px" }}
          />
          <button onClick={doDelete} disabled={busy} style={{ border: "none", background: "#b3492f", color: "#fff", borderRadius: 10, padding: "10px 14px", fontSize: 13, fontWeight: 700, cursor: "pointer", opacity: busy ? 0.7 : 1 }}>
            {busy ? "lösche …" : "Endgültig löschen"}
          </button>
          <button onClick={() => { setOpen(false); setPw(""); setErr(""); }} style={{ border: "none", background: "transparent", color: "#6b7280", fontSize: 13, cursor: "pointer" }}>
            Abbrechen
          </button>
        </div>
      )}
      {err && <div style={{ fontSize: 12.5, color: "#b3492f", marginTop: 8 }}>{err}</div>}
    </div>
  );
}
