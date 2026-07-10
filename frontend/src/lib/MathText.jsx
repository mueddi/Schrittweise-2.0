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

// Rendert Text mit eingebetteten Formeln. Erkennt:
//   $...$  und  \(...\)  -> inline
//   $$...$$ und \[...\]  -> display
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

export default function MathText({ text, style }) {
  const html = useMemo(() => {
    if (!text) return "";
    const parts = [];
    const regex = /\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\$([^$\n]+?)\$|\\\(([\s\S]+?)\\\)/g;
    let last = 0;
    let m;
    while ((m = regex.exec(text)) !== null) {
      if (m.index > last) parts.push(inlineMarkdown(escapeHtml(text.slice(last, m.index))));
      const display = m[1] !== undefined || m[2] !== undefined;
      const body = m[1] ?? m[2] ?? m[3] ?? m[4] ?? "";
      parts.push(renderMath(body, display));
      last = regex.lastIndex;
    }
    if (last < text.length) parts.push(inlineMarkdown(escapeHtml(text.slice(last))));
    return parts.join("").replace(/\n/g, "<br/>");
  }, [text]);

  return <span style={style} dangerouslySetInnerHTML={{ __html: html }} />;
}
