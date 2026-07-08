import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";

export default function LoginVerify() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const { login } = useAuth();
  const [error, setError] = useState(null);
  const done = useRef(false);

  useEffect(() => {
    if (done.current) return;
    done.current = true;
    const token = params.get("token");
    if (!token) {
      setError("Kein Token im Link.");
      return;
    }
    api
      .post("/api/auth/verify", { token })
      .then(async (res) => {
        await login(res.access_token, res.user);
        nav(res.user.role === "parent" ? "/eltern" : "/app/lernen", { replace: true });
      })
      .catch((err) => setError(err.message));
  }, [params, nav, login]);

  return (
    <div style={{ display: "grid", placeItems: "center", height: "100vh" }}>
      {error ? (
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Login fehlgeschlagen</div>
          <div style={{ fontSize: 14, color: "#6b7280", marginBottom: 16 }}>{error}</div>
          <Link to="/login" className="btn-primary" style={{ padding: "10px 18px", borderRadius: 11, fontSize: 14 }}>
            Neuen Link anfordern
          </Link>
        </div>
      ) : (
        <div style={{ color: "#9aa0ab", fontSize: 14 }}>melde dich an …</div>
      )}
    </div>
  );
}
