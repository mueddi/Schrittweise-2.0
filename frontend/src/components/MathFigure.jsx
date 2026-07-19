import { useLang } from "../lib/i18n.jsx";

// Deterministische Lern-Skizzen: die KI liefert nur winzige JSON-Parameter,
// GEZEICHNET wird hier – präzise, einheitlicher Look, sicher (reines JSX,
// es wird nie KI-Markup als HTML gerendert). Kaputte Werte -> null (nichts).

const INDIGO = "#6366f1";
const FILL = "#c9ccf6";
const TEXT = "#1a1c22";
const GRAY = "#6b7280";
const GREEN = "#1a7f3c";

const num = (v, lo, hi) => {
  const n = Number(v);
  return Number.isFinite(n) && n >= lo && n <= hi ? n : null;
};
const str = (v, max = 14) => (typeof v === "string" || typeof v === "number" ? String(v).slice(0, max) : null);

function Box({ children, w = 320, h = 180 }) {
  return (
    <span style={{ display: "block", background: "#f7f8ff", border: "1px solid #e0e2fb", borderLeft: `3px solid ${INDIGO}`, borderRadius: 12, padding: "10px 12px", margin: "8px 0", maxWidth: "100%" }}>
      <svg viewBox={`0 0 ${w} ${h}`} style={{ display: "block", width: "100%", maxWidth: w, height: "auto", margin: "0 auto" }} role="img">
        {children}
      </svg>
    </span>
  );
}

const T = ({ x, y, size = 13, fill = TEXT, anchor = "middle", bold, children }) => (
  <text x={x} y={y} fontSize={size} fill={fill} textAnchor={anchor} fontWeight={bold ? 700 : 500} fontFamily="Inter, system-ui, sans-serif">{children}</text>
);

// 1) Bruch: Pizza + Balken
function Bruch({ zaehler, nenner }) {
  const { t } = useLang();
  const n = num(nenner, 1, 24);
  const z = zaehler === 0 ? 0 : num(zaehler, 0, 24);
  if (n === null || z === null || z > n) return null;
  const cx = 78, cy = 88, r = 58;
  const slice = (i, filled) => {
    if (n === 1) return <circle key={i} cx={cx} cy={cy} r={r} fill={filled ? FILL : "#fff"} stroke={INDIGO} strokeWidth="1.6" />;
    const a0 = (i / n) * 2 * Math.PI - Math.PI / 2;
    const a1 = ((i + 1) / n) * 2 * Math.PI - Math.PI / 2;
    const d = `M ${cx} ${cy} L ${cx + r * Math.cos(a0)} ${cy + r * Math.sin(a0)} A ${r} ${r} 0 0 1 ${cx + r * Math.cos(a1)} ${cy + r * Math.sin(a1)} Z`;
    return <path key={i} d={d} fill={filled ? FILL : "#fff"} stroke={INDIGO} strokeWidth="1.4" />;
  };
  const bw = 130, bx = 168, by = 66, bh = 34;
  return (
    <Box h={176}>
      {Array.from({ length: n }, (_, i) => slice(i, i < z))}
      {Array.from({ length: n }, (_, i) => (
        <rect key={`b${i}`} x={bx + (i * bw) / n} y={by} width={bw / n} height={bh} fill={i < z ? FILL : "#fff"} stroke={INDIGO} strokeWidth="1.2" />
      ))}
      <T x={bx + bw / 2} y={by + bh + 24} size={17} bold>{z}/{n}</T>
      <T x={bx + bw / 2} y={by - 14} size={12} fill={GRAY}>{t(`${z} von ${n} Teilen`, `${z} of ${n} parts`)}</T>
    </Box>
  );
}

// 2) Zahlenstrahl
function Zahlenstrahl({ von, bis, punkte }) {
  const a = num(von, -1000, 1000);
  const b = num(bis, -1000, 1000);
  if (a === null || b === null || b <= a || b - a > 50) return null;
  const marks = Array.isArray(punkte) ? punkte.map((p) => num(p, a, b)).filter((p) => p !== null).slice(0, 8) : [];
  const x0 = 22, x1 = 298, y = 92;
  const px = (v) => x0 + ((v - a) / (b - a)) * (x1 - x0);
  const step = Math.max(1, Math.ceil((b - a) / 12));
  const ticks = [];
  for (let v = a; v <= b; v += step) ticks.push(v);
  return (
    <Box h={150}>
      <line x1={x0 - 8} y1={y} x2={x1 + 8} y2={y} stroke={TEXT} strokeWidth="1.6" />
      <polygon points={`${x1 + 8},${y} ${x1 - 1},${y - 5} ${x1 - 1},${y + 5}`} fill={TEXT} />
      {ticks.map((v) => (
        <g key={v}>
          <line x1={px(v)} y1={y - 6} x2={px(v)} y2={y + 6} stroke={TEXT} strokeWidth="1.2" />
          <T x={px(v)} y={y + 24} size={12} fill={GRAY}>{v}</T>
        </g>
      ))}
      {marks.map((v, i) => (
        <g key={`m${i}`}>
          <circle cx={px(v)} cy={y} r={6} fill={INDIGO} />
          <T x={px(v)} y={y - 16} size={13} fill={INDIGO} bold>{v}</T>
        </g>
      ))}
    </Box>
  );
}

// 3) Waage (Gleichung im Gleichgewicht)
function Waage({ links, rechts }) {
  const { t } = useLang();
  const l = str(links, 16);
  const r = str(rechts, 16);
  if (!l || !r) return null;
  return (
    <Box h={168}>
      <line x1="160" y1="34" x2="160" y2="120" stroke={TEXT} strokeWidth="3" />
      <polygon points="130,132 190,132 160,118" fill={GRAY} />
      <rect x="120" y="128" width="80" height="8" rx="3" fill={TEXT} />
      <line x1="52" y1="34" x2="268" y2="34" stroke={TEXT} strokeWidth="3" />
      {/* Schalen */}
      <line x1="52" y1="34" x2="52" y2="58" stroke={GRAY} strokeWidth="1.6" />
      <line x1="268" y1="34" x2="268" y2="58" stroke={GRAY} strokeWidth="1.6" />
      <path d="M 18 58 Q 52 88 86 58 Z" fill={FILL} stroke={INDIGO} strokeWidth="1.5" />
      <path d="M 234 58 Q 268 88 302 58 Z" fill={FILL} stroke={INDIGO} strokeWidth="1.5" />
      <T x={52} y={76} size={14} bold>{l}</T>
      <T x={268} y={76} size={14} bold>{r}</T>
      <T x={160} y={158} size={12} fill={GRAY}>{t("beide Seiten bleiben im Gleichgewicht", "both sides stay in balance")}</T>
    </Box>
  );
}

// 4) Rechteck mit beschrifteten Seiten
function Rechteck({ a, b, flaeche }) {
  const la = str(a, 10);
  const lb = str(b, 10);
  if (la === null || lb === null) return null;
  return (
    <Box h={176}>
      <rect x="70" y="30" width="180" height="110" fill={FILL} fillOpacity="0.5" stroke={INDIGO} strokeWidth="1.8" />
      <T x={160} y={162} size={14} bold>a = {la}</T>
      <T x={272} y={90} size={14} bold anchor="start">b = {lb}</T>
      {flaeche != null && str(flaeche, 12) !== null && <T x={160} y={92} size={15} fill={INDIGO} bold>A = {str(flaeche, 12)}</T>}
    </Box>
  );
}

// 5) Dreieck (bei gueltigen Zahlen massstabsgetreu, sonst generische Form)
function Dreieck({ a, b, c, rechtwinklig }) {
  const la = str(a, 8), lb = str(b, 8), lc = str(c, 8);
  if (la === null && lb === null && lc === null) return null;
  const na = num(a, 0.1, 10000), nb = num(b, 0.1, 10000), nc = num(c, 0.1, 10000);
  // Ecken: A links unten, B rechts unten (Basis c), C oben
  let A = [40, 150], B = [280, 150], C = [110, 40];
  if (rechtwinklig) {
    C = [40, 45];
  } else if (na && nb && nc && na + nb > nc && na + nc > nb && nb + nc > na) {
    const x = (nb * nb + nc * nc - na * na) / (2 * nc);
    const y = Math.sqrt(Math.max(nb * nb - x * x, 0.01));
    const scale = Math.min(240 / nc, 105 / y);
    A = [40, 150]; B = [40 + nc * scale, 150]; C = [40 + x * scale, 150 - y * scale];
  }
  const mid = (P, Q) => [(P[0] + Q[0]) / 2, (P[1] + Q[1]) / 2];
  const [mcx, mcy] = mid(A, B), [max_, may] = mid(B, C), [mbx, mby] = mid(A, C);
  return (
    <Box h={176}>
      <polygon points={`${A[0]},${A[1]} ${B[0]},${B[1]} ${C[0]},${C[1]}`} fill={FILL} fillOpacity="0.5" stroke={INDIGO} strokeWidth="1.8" />
      {rechtwinklig && <path d={`M ${A[0] + 14} ${A[1]} L ${A[0] + 14} ${A[1] - 14} L ${A[0]} ${A[1] - 14}`} fill="none" stroke={TEXT} strokeWidth="1.4" />}
      {lc !== null && <T x={mcx} y={mcy + 20} size={14} bold>{lc}</T>}
      {la !== null && <T x={max_ + 14} y={may} size={14} bold anchor="start">{la}</T>}
      {lb !== null && <T x={mbx - 14} y={mby} size={14} bold anchor="end">{lb}</T>}
    </Box>
  );
}

// 6) Koordinatensystem mit Punkten und optionaler Gerade
function Koordinaten({ punkte, gerade }) {
  const pts = Array.isArray(punkte)
    ? punkte.map((p) => (Array.isArray(p) && p.length === 2 ? [num(p[0], -10, 10), num(p[1], -10, 10)] : null))
        .filter((p) => p && p[0] !== null && p[1] !== null).slice(0, 10)
    : [];
  const m = gerade ? num(gerade.m, -50, 50) : null;
  const q = gerade ? num(gerade.q, -50, 50) : null;
  if (!pts.length && m === null) return null;
  const R = 5; // sichtbarer Bereich -5..5
  const cx = 160, cy = 95, u = 17; // Einheit in px
  const X = (x) => cx + x * u, Y = (y) => cy - y * u;
  const gridEls = [];
  for (let i = -R; i <= R; i++) {
    gridEls.push(<line key={`v${i}`} x1={X(i)} y1={Y(-R)} x2={X(i)} y2={Y(R)} stroke="#e3e5f2" strokeWidth="1" />);
    gridEls.push(<line key={`h${i}`} x1={X(-R)} y1={Y(i)} x2={X(R)} y2={Y(i)} stroke="#e3e5f2" strokeWidth="1" />);
  }
  let lineEl = null;
  if (m !== null && q !== null) {
    const y1 = m * -R + q, y2 = m * R + q;
    lineEl = <line x1={X(-R)} y1={Y(y1)} x2={X(R)} y2={Y(y2)} stroke={GREEN} strokeWidth="2" />;
  }
  return (
    <Box h={190}>
      <g clipPath="url(#kb)">
        <defs><clipPath id="kb"><rect x={X(-R)} y={Y(R)} width={2 * R * u} height={2 * R * u} /></clipPath></defs>
        {gridEls}
        {lineEl}
      </g>
      <line x1={X(-R) - 4} y1={cy} x2={X(R) + 8} y2={cy} stroke={TEXT} strokeWidth="1.5" />
      <line x1={cx} y1={Y(-R) + 4} x2={cx} y2={Y(R) - 8} stroke={TEXT} strokeWidth="1.5" />
      <T x={X(R) + 6} y={cy - 6} size={11} fill={GRAY} anchor="end">x</T>
      <T x={cx + 8} y={Y(R) - 1} size={11} fill={GRAY} anchor="start">y</T>
      <T x={X(1)} y={cy + 13} size={9.5} fill={GRAY}>1</T>
      <T x={cx - 7} y={Y(1) + 3} size={9.5} fill={GRAY}>1</T>
      {pts.map(([x, y], i) => (
        <g key={i}>
          <circle cx={X(x)} cy={Y(y)} r={4.5} fill={INDIGO} />
          <T x={X(x)} y={Y(y) - 9} size={11} fill={INDIGO} bold>({x}|{y})</T>
        </g>
      ))}
    </Box>
  );
}

// 7) Winkel
function Winkel({ grad }) {
  const g = num(grad, 1, 359);
  if (g === null) return null;
  const cx = 90, cy = 140, len = 120, r = 42;
  const rad = (-g * Math.PI) / 180;
  const ex = cx + len * Math.cos(rad), ey = cy + len * Math.sin(rad);
  const ax = cx + r * Math.cos(rad), ay = cy + r * Math.sin(rad);
  const large = g > 180 ? 1 : 0;
  return (
    <Box h={170}>
      <line x1={cx} y1={cy} x2={cx + len} y2={cy} stroke={TEXT} strokeWidth="2" />
      <line x1={cx} y1={cy} x2={ex} y2={ey} stroke={TEXT} strokeWidth="2" />
      <path d={`M ${cx + r} ${cy} A ${r} ${r} 0 ${large} 0 ${ax} ${ay}`} fill="none" stroke={INDIGO} strokeWidth="2" />
      <T x={cx + r + 26} y={cy - 14 - (g > 120 ? 0 : g / 8)} size={15} fill={INDIGO} bold>{g}°</T>
      <circle cx={cx} cy={cy} r={3} fill={TEXT} />
    </Box>
  );
}

// 8) Kreis mit Radius oder Durchmesser
function Kreis({ radius, durchmesser }) {
  const lr = radius != null ? str(radius, 10) : null;
  const ld = durchmesser != null ? str(durchmesser, 10) : null;
  if (lr === null && ld === null) return null;
  const cx = 160, cy = 92, r = 62;
  return (
    <Box h={184}>
      <circle cx={cx} cy={cy} r={r} fill={FILL} fillOpacity="0.4" stroke={INDIGO} strokeWidth="1.8" />
      <circle cx={cx} cy={cy} r={2.6} fill={TEXT} />
      {lr !== null ? (
        <g>
          <line x1={cx} y1={cy} x2={cx + r} y2={cy} stroke={TEXT} strokeWidth="1.6" />
          <T x={cx + r / 2} y={cy - 8} size={14} bold>r = {lr}</T>
        </g>
      ) : (
        <g>
          <line x1={cx - r} y1={cy} x2={cx + r} y2={cy} stroke={TEXT} strokeWidth="1.6" />
          <T x={cx} y={cy - 8} size={14} bold>d = {ld}</T>
        </g>
      )}
    </Box>
  );
}

// 9) Prozentbalken
function Prozentbalken({ prozent }) {
  const p = num(prozent, 0, 100);
  if (p === null) return null;
  const x = 24, w = 272, y = 58, h = 36;
  return (
    <Box h={130}>
      <rect x={x} y={y} width={w} height={h} rx="8" fill="#fff" stroke={INDIGO} strokeWidth="1.5" />
      <rect x={x} y={y} width={(w * p) / 100} height={h} rx="8" fill={FILL} stroke={INDIGO} strokeWidth="1.2" />
      <T x={x + (w * p) / 100} y={y - 10} size={15} fill={INDIGO} bold>{p}%</T>
      <T x={x} y={y + h + 20} size={11} fill={GRAY} anchor="start">0%</T>
      <T x={x + w} y={y + h + 20} size={11} fill={GRAY} anchor="end">100%</T>
    </Box>
  );
}

// 10) Saeulendiagramm
function Saeulen({ werte, labels }) {
  const vals = Array.isArray(werte) ? werte.map((v) => num(v, 0, 100000)).filter((v) => v !== null).slice(0, 8) : [];
  if (vals.length < 2) return null;
  const labs = Array.isArray(labels) ? labels.map((l) => str(l, 6)) : [];
  const maxV = Math.max(...vals);
  const x0 = 34, baseY = 140, cw = 272 / vals.length;
  return (
    <Box h={176}>
      <line x1={x0 - 8} y1={baseY} x2={x0 + 272} y2={baseY} stroke={TEXT} strokeWidth="1.4" />
      {vals.map((v, i) => {
        const h = maxV > 0 ? (v / maxV) * 96 : 0;
        const bw = Math.min(cw * 0.62, 44);
        const bx = x0 + i * cw + (cw - bw) / 2;
        return (
          <g key={i}>
            <rect x={bx} y={baseY - h} width={bw} height={h} rx="4" fill={FILL} stroke={INDIGO} strokeWidth="1.2" />
            <T x={bx + bw / 2} y={baseY - h - 6} size={12} fill={INDIGO} bold>{v}</T>
            {labs[i] && <T x={bx + bw / 2} y={baseY + 18} size={11.5} fill={GRAY}>{labs[i]}</T>}
          </g>
        );
      })}
    </Box>
  );
}

// 11) General-Vorlage: beliebige Figur aus Punkten/Linien/Labels (0-100)
function Figur({ punkte, linien, labels }) {
  const pts = Array.isArray(punkte)
    ? punkte.map((p) => (Array.isArray(p) && p.length === 2 ? [num(p[0], -1000, 1000), num(p[1], -1000, 1000)] : null))
        .filter((p) => p && p[0] !== null && p[1] !== null).slice(0, 20)
    : [];
  if (pts.length < 2) return null;
  // Bounding Box -> Zeichenflaeche einpassen (y-Achse mathematisch, also invertiert)
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const spanX = Math.max(maxX - minX, 0.001), spanY = Math.max(maxY - minY, 0.001);
  const scale = Math.min(250 / spanX, 120 / spanY);
  const offX = 160 - ((minX + maxX) / 2) * scale;
  const offY = 92 + ((minY + maxY) / 2) * scale;
  const P = pts.map(([x, y]) => [x * scale + offX, offY - y * scale]);
  const edges = Array.isArray(linien)
    ? linien.map((l) => (Array.isArray(l) && l.length === 2 ? [num(l[0], 0, pts.length - 1), num(l[1], 0, pts.length - 1)] : null))
        .filter((l) => l && l[0] !== null && l[1] !== null && Number.isInteger(l[0]) && Number.isInteger(l[1])).slice(0, 40)
    : null;
  const labs = Array.isArray(labels)
    ? labels.map((l) => (l && typeof l === "object" ? { x: num(l.x, -1000, 1000), y: num(l.y, -1000, 1000), text: str(l.text, 12) } : null))
        .filter((l) => l && l.x !== null && l.y !== null && l.text).slice(0, 12)
    : [];
  return (
    <Box h={184}>
      {edges && edges.length ? (
        edges.map(([i, j], k) => (
          <line key={k} x1={P[i][0]} y1={P[i][1]} x2={P[j][0]} y2={P[j][1]} stroke={INDIGO} strokeWidth="1.8" />
        ))
      ) : (
        <polygon points={P.map((p) => p.join(",")).join(" ")} fill={FILL} fillOpacity="0.5" stroke={INDIGO} strokeWidth="1.8" />
      )}
      {labs.map((l, k) => (
        <T key={k} x={l.x * scale + offX} y={offY - l.y * scale} size={13.5} bold>{l.text}</T>
      ))}
    </Box>
  );
}

const RENDERERS = {
  bruch: Bruch,
  zahlenstrahl: Zahlenstrahl,
  waage: Waage,
  rechteck: Rechteck,
  dreieck: Dreieck,
  koordinaten: Koordinaten,
  winkel: Winkel,
  kreis: Kreis,
  prozentbalken: Prozentbalken,
  saeulen: Saeulen,
  figur: Figur,
};

export default function MathFigure({ spec }) {
  if (!spec || typeof spec !== "object") return null;
  const R = RENDERERS[spec.typ];
  if (!R) return null;
  try {
    return <R {...spec} />;
  } catch {
    return null; // kaputte Parameter: Skizze still weglassen
  }
}
