import { useMemo } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";

const escapeHtml = (s) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

// Minimales, sicheres Markdown auf bereits ESCAPETEM Text:
// **fett** -> <strong>, *kursiv* -> <em> (nur wenn kein Leerzeichen an den
// Raendern – so bleibt 3*x*2 unangetastet). Mehr Markdown gibt es bewusst
// nicht; der Tutor-Prompt verbietet Titel/Tabellen.
function inlineMarkdown(escaped) {
  return escaped
    .replace(/\*\*([^*\n]+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[\s(])\*([^\s*][^*\n]*?[^\s*]|[^\s*])\*(?=[\s.,:;!?)]|$)/gm, "$1<em>$2</em>");
}

// Lineare Schreibweise -> LaTeX, damit KaTeX sie schoen setzt:
// 3*x -> 3·x, 1/2 -> Bruch, sqrt(16) -> Wurzel, <= / >= / != -> ≤ ≥ ≠.
// Wird NICHT angewendet, wenn der Ausdruck schon echtes LaTeX ist (Backslash).
function linearToLatex(src) {
  let s = src;
  s = s.replace(/sqrt\(([^()]*(?:\([^()]*\)[^()]*)*)\)/gi, "\\sqrt{$1}");
  // einfache Brueche: Zahl/Variable/geklammerte Gruppe auf beiden Seiten
  const tok = "(\\([^()]+\\)|\\d+(?:[.,]\\d+)?|[a-zA-Z])";
  const strip = (t) => (t.startsWith("(") && t.endsWith(")") ? t.slice(1, -1) : t);
  s = s.replace(
    new RegExp(`${tok}\\s*/\\s*${tok}`, "g"),
    (_, a, b) => `\\frac{${strip(a)}}{${strip(b)}}`
  );
  s = s.replace(/<=/g, "\\le ").replace(/>=/g, "\\ge ").replace(/!=/g, "\\ne ");
  s = s.replace(/\*/g, "\\cdot ");
  return s;
}

// Alles andere bleibt normaler Text. Robust gegen KaTeX-Fehler.
function renderMath(src, displayMode) {
  try {
    return katex.renderToString(src, { throwOnError: false, displayMode });
  } catch {
    // Wirft KaTeX doch (nicht-Parse-Fehler), den Rohtext ESCAPEN – niemals
    // ungefiltert als HTML einsetzen (sonst XSS ueber $...$-Nutzereingaben).
    return escapeHtml(src);
  }
}

// Sieht ein Kandidat wirklich nach Mathe aus? Konservativ, damit normaler
// Text («Seite 3-4», «Klasse 2», Jahreszahlen) niemals als Formel endet.
function isMathy(c) {
  if (/[=<>]/.test(c)) return true; // Gleichung/Ungleichung
  if (/[*/^]/.test(c)) return true; // 3*4, 1/2, x^2
  if (/sqrt\(/i.test(c)) return true;
  if (/[+\-]/.test(c) && /\d[a-zA-Z]|[a-zA-Z]\d/.test(c)) return true; // 3x + 5
  return false;
}

// Text-Chunk OHNE echte Woerter: nackte Mathe-Ausdruecke finden und rendern.
function scanChunk(chunk) {
  const re = /[0-9a-zA-Z(][0-9a-zA-Z+\-*/^=<>()., ]*/g;
  let out = "";
  let last = 0;
  let m;
  while ((m = re.exec(chunk)) !== null) {
    // Satzzeichen/haengende Operatoren am Ende gehoeren nicht in die Formel
    const cand = m[0].replace(/[\s.,:;*+\-/^=<>]+$/g, "");
    if (cand && isMathy(cand)) {
      out += escapeHtml(chunk.slice(last, m.index));
      out += renderMath(linearToLatex(cand), false);
      out += escapeHtml(m[0].slice(cand.length));
    } else {
      out += escapeHtml(chunk.slice(last, m.index) + m[0]);
    }
    last = re.lastIndex;
  }
  return out + escapeHtml(chunk.slice(last));
}

// Textsegment (ausserhalb $...$): Woerter (>=3 Buchstaben) bleiben Text,
// dazwischen wird nach nackter Mathe gesucht. «sqrt» zaehlt nicht als Wort.
function plainSegment(raw) {
  const parts = raw.split(/(\b(?!sqrt\b)[A-Za-zÀ-ÿ]{3,}\b)/);
  let out = "";
  for (let i = 0; i < parts.length; i++) {
    out += i % 2 === 1 ? escapeHtml(parts[i]) : scanChunk(parts[i]);
  }
  return out;
}

// Zeilen-Nachbearbeitung: Leerzeile -> Absatz-Abstand, «- …» -> Aufzaehlung.
function withLines(html) {
  const out = [];
  for (const line of html.split("\n")) {
    const t = line.trim();
    if (t === "") {
      out.push('<span class="mt-par"></span>');
      continue;
    }
    const li = t.match(/^-\s+([\s\S]*)$/);
    if (li) {
      out.push(`<span class="mt-li">${li[1]}</span>`);
      continue;
    }
    out.push(line + "<br/>");
  }
  return out
    .join("")
    .replace(/<br\/>(<span class="mt-(?:par|li))/g, "$1") // kein Doppelabstand vor Bloecken
    .replace(/(<span class="mt-par"><\/span>){2,}/g, "$1") // mehrere Leerzeilen = 1 Absatz
    .replace(/(?:<br\/>)+$/g, "");
}

// Rendert Text mit eingebetteten Formeln. Erkennt:
//   $...$  und  \(...\)  -> inline
//   $$...$$ und \[...\]  -> display
// plus Auto-Erkennung nackter Mathe (3x + 5 = 20) im normalen Text.
function buildHtml(text) {
  if (!text) return "";
  const parts = [];
  const regex = /\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\$([^$\n]+?)\$|\\\(([\s\S]+?)\\\)/g;
  let last = 0;
  let m;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) parts.push(plainSegment(text.slice(last, m.index)));
    const display = m[1] !== undefined || m[2] !== undefined;
    const body = m[1] ?? m[2] ?? m[3] ?? m[4] ?? "";
    parts.push(renderMath(body.includes("\\") ? body : linearToLatex(body), display));
    last = regex.lastIndex;
  }
  if (last < text.length) parts.push(plainSegment(text.slice(last)));
  return withLines(inlineMarkdown(parts.join("")));
}

export default function MathText({ text, style }) {
  const html = useMemo(() => buildHtml(text), [text]);
  return <span style={style} dangerouslySetInnerHTML={{ __html: html }} />;
}
