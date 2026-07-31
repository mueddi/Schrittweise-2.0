// Welche Sprache soll die App sprechen?
//
// Reihenfolge: manuelle Wahl (localStorage) > Browser-Sprache. Nach dem Login
// gewinnt das Profil, das regelt i18n.jsx.
//
// Diese fünf Zeilen standen wortgleich in api.js UND in i18n.jsx – wer eine
// änderte, hatte zwei verschiedene Regeln. Sie liegen hier in einer eigenen
// Datei, weil api.js nicht aus i18n.jsx importieren kann: i18n.jsx importiert
// bereits api.js, das gäbe einen Ring.
export function detectLang() {
  const stored = localStorage.getItem("sw_lang");
  if (stored === "de" || stored === "en") return stored;
  const langs = navigator.languages?.length ? navigator.languages : [navigator.language || "de"];
  return langs.some((l) => String(l).toLowerCase().startsWith("de")) ? "de" : "en";
}
