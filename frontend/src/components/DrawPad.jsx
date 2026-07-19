import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api.js";

// Zeichenfläche für Stift-/Finger-Eingabe: Striche werden als Bild an die
// OCR-Erkennung geschickt; das Ergebnis landet editierbar im Chat-Eingabefeld.
export default function DrawPad({ onResult, onClose }) {
  const canvasRef = useRef(null);
  const wrapRef = useRef(null);
  const strokes = useRef([]); // Array von Strichen (je Array von Punkten) für Rückgängig
  const current = useRef(null);
  const [hasInk, setHasInk] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  // Canvas an Containergrösse anpassen (einmalig + bei Resize), Striche neu zeichnen
  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const { width, height } = wrap.getBoundingClientRect();
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      redraw();
    };
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  function ctx2d() {
    return canvasRef.current.getContext("2d");
  }

  function redraw() {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = ctx2d();
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "#1a1c22";
    ctx.lineWidth = 3.2;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    for (const stroke of strokes.current) {
      if (stroke.length < 2) {
        // Punkt (z.B. Dezimalpunkt) sichtbar machen
        ctx.beginPath();
        ctx.arc(stroke[0].x, stroke[0].y, 1.4, 0, Math.PI * 2);
        ctx.fillStyle = "#1a1c22";
        ctx.fill();
        continue;
      }
      ctx.beginPath();
      ctx.moveTo(stroke[0].x, stroke[0].y);
      for (const p of stroke.slice(1)) ctx.lineTo(p.x, p.y);
      ctx.stroke();
    }
  }

  function pos(e) {
    const rect = canvasRef.current.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }

  function down(e) {
    e.preventDefault();
    canvasRef.current.setPointerCapture?.(e.pointerId);
    current.current = [pos(e)];
  }
  function move(e) {
    if (!current.current) return;
    e.preventDefault();
    current.current.push(pos(e));
    // Strich live zeichnen (voller Redraw erst beim Absetzen)
    const ctx = ctx2d();
    const pts = current.current;
    const a = pts[pts.length - 2] || pts[pts.length - 1];
    const b = pts[pts.length - 1];
    ctx.strokeStyle = "#1a1c22";
    ctx.lineWidth = 3.2;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
  }
  function up() {
    if (!current.current) return;
    strokes.current.push(current.current);
    current.current = null;
    setHasInk(true);
    redraw();
  }

  function undo() {
    strokes.current.pop();
    setHasInk(strokes.current.length > 0);
    redraw();
  }
  function clearAll() {
    strokes.current = [];
    setHasInk(false);
    redraw();
  }

  // Export in hoher Aufloesung: die Striche auf einen Offscreen-Canvas mit
  // mind. 2x-Massstab neu zeichnen – mehr Pixel = deutlich bessere Erkennung
  // (der sichtbare Canvas hat nur Bildschirmaufloesung).
  function exportBlob() {
    const { width, height } = wrapRef.current.getBoundingClientRect();
    const scale = Math.max(window.devicePixelRatio || 1, 2);
    const out = document.createElement("canvas");
    out.width = Math.round(width * scale);
    out.height = Math.round(height * scale);
    const ctx = out.getContext("2d");
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, width, height);
    ctx.strokeStyle = "#1a1c22";
    ctx.lineWidth = 3.2;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    for (const stroke of strokes.current) {
      if (stroke.length < 2) {
        ctx.beginPath();
        ctx.arc(stroke[0].x, stroke[0].y, 1.4, 0, Math.PI * 2);
        ctx.fillStyle = "#1a1c22";
        ctx.fill();
        continue;
      }
      ctx.beginPath();
      ctx.moveTo(stroke[0].x, stroke[0].y);
      for (const p of stroke.slice(1)) ctx.lineTo(p.x, p.y);
      ctx.stroke();
    }
    return new Promise((resolve) => out.toBlob(resolve, "image/png"));
  }

  async function recognize() {
    if (!hasInk || busy) return;
    setBusy(true);
    setError(null);
    try {
      const blob = await exportBlob();
      const fd = new FormData();
      fd.append("file", blob, "stift-eingabe.png");
      const res = await api.upload("/api/exercises/ocr", fd);
      // Vollen erkannten Text nehmen – math_expression ist nur ein per Regex
      // herausgezogenes Fragment (mit «=») und verstuemmelt mehrzeilige Rechnungen.
      const text = (res.text || res.math_expression || "").trim();
      if (!text && !res.image_path) {
        setError("Konnte nichts erkennen – schreib etwas grösser und deutlicher.");
        return;
      }
      // Zeichnung haengt als Bild an der Nachricht – auch ohne erkannten Text
      onResult({ text, imagePath: res.image_path || null });
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const btn = {
    border: "1px solid #d2d4dd",
    background: "#fff",
    borderRadius: 10,
    padding: "9px 14px",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  };

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(20,22,30,.45)", zIndex: 60, display: "grid", placeItems: "center", padding: 14 }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={{ background: "#fff", borderRadius: 18, width: "min(680px, 100%)", display: "flex", flexDirection: "column", overflow: "hidden", boxShadow: "0 20px 60px rgba(20,22,30,.25)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 18px", borderBottom: "1px solid #eef0f3" }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 800 }}>✍️ Mit dem Stift schreiben</div>
            <div style={{ fontSize: 12, color: "#9aa0ab" }}>Schreib oder zeichne – ich lese es, und deine Zeichnung hängt als Bild an der Nachricht.</div>
          </div>
          <button onClick={onClose} style={{ border: "none", background: "transparent", fontSize: 18, color: "#9aa0ab", cursor: "pointer" }}>✕</button>
        </div>

        <div ref={wrapRef} style={{ height: "min(46vh, 340px)", background: "#fff", touchAction: "none", cursor: "crosshair", borderBottom: "1px solid #eef0f3", backgroundImage: "repeating-linear-gradient(#fff, #fff 34px, #f0f1f6 35px)" }}>
          <canvas
            ref={canvasRef}
            onPointerDown={down}
            onPointerMove={move}
            onPointerUp={up}
            onPointerCancel={up}
            style={{ display: "block", touchAction: "none" }}
          />
        </div>

        {error && (
          <div style={{ margin: "10px 18px 0", fontSize: 13, background: "#fdecec", color: "#c0392b", border: "1px solid #f5cccc", borderRadius: 10, padding: "8px 12px" }}>{error}</div>
        )}

        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 18px" }}>
          <button onClick={undo} disabled={!hasInk} style={{ ...btn, opacity: hasInk ? 1 : 0.5 }}>↩ Rückgängig</button>
          <button onClick={clearAll} disabled={!hasInk} style={{ ...btn, opacity: hasInk ? 1 : 0.5 }}>🗑 Löschen</button>
          <button
            onClick={recognize}
            disabled={!hasInk || busy}
            className="btn-primary"
            style={{ marginLeft: "auto", borderRadius: 10, padding: "10px 18px", fontSize: 13, opacity: !hasInk || busy ? 0.6 : 1 }}
          >
            {busy ? "wird gelesen …" : "✓ Übernehmen"}
          </button>
        </div>
      </div>
    </div>
  );
}
