import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";
import { useLang } from "../lib/i18n.jsx";

export default function LoginVerify() {
  const { t } = useLang();
  const [params] = useSearchParams();
  const nav = useNavigate();
  const { login } = useAuth();
  const [error, setError] = useState(null);
  const done = useRef(false);

  useEffect(() => {
    if (done.current) return;
    done.current = true;

    const finish = async (res) => {
      await login(res.access_token, res.user);
      nav(res.user.role === "parent" ? "/eltern" : "/app/lernen", { replace: true });
    };

    // Supabase-Magic-Link: Token kommt im URL-Fragment zurück
    // (#access_token=…&type=magiclink) und wird gegen das App-JWT getauscht.
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const sbToken = hash.get("access_token");
    const sbError = hash.get("error_description");
    const token = params.get("token");

    if (sbToken) {
      // Fragment aus der Adresszeile entfernen, damit das Token nirgends hängen bleibt
      window.history.replaceState(null, "", window.location.pathname);
      api
        .post("/api/auth/verify-supabase", { access_token: sbToken })
        .then(finish)
        .catch((err) => setError(err.message));
    } else if (token) {
      api
        .post("/api/auth/verify", { token })
        .then(finish)
        .catch((err) => setError(err.message));
    } else {
      setError(sbError || t("Kein Token im Link.", "No token in the link."));
    }
  }, [params, nav, login]);

  return (
    <div style={{ display: "grid", placeItems: "center", height: "100vh" }}>
      {error ? (
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>{t("Login fehlgeschlagen", "Login failed")}</div>
          <div style={{ fontSize: 14, color: "#6b7280", marginBottom: 16 }}>{error}</div>
          <Link to="/login" className="btn-primary" style={{ padding: "10px 18px", borderRadius: 11, fontSize: 14 }}>
            {t("Neuen Link anfordern", "Request a new link")}
          </Link>
        </div>
      ) : (
        <div style={{ color: "#9aa0ab", fontSize: 14 }}>{t("melde dich an …", "signing you in …")}</div>
      )}
    </div>
  );
}
