// Bremse gegen Browser-Dialoge.
//
// `window.confirm` / `window.alert` / `window.prompt` zeichnet der BROWSER –
// grau, in der Schrift des Systems, mit dem Vorspann «… sagt:», nicht
// uebersetzbar und nicht gestaltbar. Genau das hat der Betreiber gemeldet
// («komische meldungen mit einem häslichen aussehen»). Ersetzt sind sie durch
// `useDialog()` aus `src/lib/dialog.jsx`.
//
// Dieses Skript haengt in `npm run build` – es greift damit lokal, in ci.yml
// und in deploy.yml gleichermassen, ohne dass jemand daran denken muss.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const WURZEL = new URL("../src", import.meta.url).pathname;
const VERBOTEN = /(?:window\s*\.\s*(?:confirm|alert|prompt)|(?<![.\w$])(?:confirm|alert)\s*\()/;

function dateien(pfad) {
  return readdirSync(pfad).flatMap((n) => {
    const p = join(pfad, n);
    return statSync(p).isDirectory() ? dateien(p) : /\.jsx?$/.test(p) ? [p] : [];
  });
}

// Kommentare zaehlen nicht – dialog.jsx erklaert in seinem eigenen Kopf,
// wovon es die App befreit, und das darf die Bremse nicht ausloesen.
const ohneKommentar = (z) => z.replace(/\/\/.*$/, "").replace(/^\s*\*.*$/, "");

const funde = [];
for (const datei of dateien(WURZEL)) {
  readFileSync(datei, "utf8").split("\n").forEach((zeile, i) => {
    if (VERBOTEN.test(ohneKommentar(zeile))) funde.push(`${datei.slice(WURZEL.length - 3)}:${i + 1}  ${zeile.trim()}`);
  });
}

if (funde.length) {
  console.error("\n✖ Browser-Dialoge gefunden – bitte useDialog() aus src/lib/dialog.jsx benutzen:\n");
  for (const f of funde) console.error("   " + f);
  console.error("\n  (bestaetigen / wahl / hinweis / eingabe – im Design der App)\n");
  process.exit(1);
}
