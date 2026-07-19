import { createContext, useContext, useState } from "react";
import { api } from "./api.js";

// Zweisprachigkeit ohne Fremd-Library: jede Stelle uebergibt beide
// Fassungen direkt – t("Deutsch …", "English …"). Sprache: manueller
// Override (localStorage) > Profil (nach Login) > Browser-Sprache.

const LangContext = createContext(null);

export function detectLang() {
  const stored = localStorage.getItem("sw_lang");
  if (stored === "de" || stored === "en") return stored;
  const langs = navigator.languages?.length ? navigator.languages : [navigator.language || "de"];
  return langs.some((l) => String(l).toLowerCase().startsWith("de")) ? "de" : "en";
}

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(detectLang);

  // Manueller Wechsel: merken + (falls eingeloggt) im Profil speichern
  const setLang = (l) => {
    setLangState(l);
    localStorage.setItem("sw_lang", l);
    if (localStorage.getItem("sw_token")) {
      api.patch("/api/auth/me", { language: l }).catch(() => {});
    }
  };

  // Profil-Sprache uebernehmen (nach Login), solange kein manueller Override existiert
  const adoptProfileLang = (l) => {
    if (!localStorage.getItem("sw_lang") && (l === "de" || l === "en") && l !== lang) {
      setLangState(l);
    }
  };

  const t = (de, en) => (lang === "en" ? en : de);

  return (
    <LangContext.Provider value={{ lang, setLang, adoptProfileLang, t }}>
      {children}
    </LangContext.Provider>
  );
}

export function useLang() {
  return useContext(LangContext);
}

// Stufen: kanonische Keys in der DB, uebersetzte Labels in der Anzeige.
export const GRADE_KEYS = ["mittelstufe", "oberstufe", "gymnasium"];

export function gradeLabel(key, lang) {
  const map = {
    mittelstufe: ["Mittelstufe (4.–6. Klasse)", "Middle school (grades 4–6)"],
    oberstufe: ["Oberstufe (7.–9. Klasse)", "Secondary school (grades 7–9)"],
    gymnasium: ["Gymnasium", "High school (Gymnasium)"],
  };
  const m = map[(key || "").toLowerCase()];
  if (m) return lang === "en" ? m[1] : m[0];
  // Alt-Werte («2. Oberstufe») unveraendert anzeigen, bis die Migration greift
  return key || (lang === "en" ? "Secondary school" : "Oberstufe");
}

// Kurz-Label (z.B. Bibliotheks-Chips)
export function gradeShort(key, lang) {
  const map = {
    mittelstufe: ["Mittelstufe", "Middle"],
    oberstufe: ["Oberstufe", "Secondary"],
    gymnasium: ["Gymi", "High school"],
  };
  const m = map[(key || "").toLowerCase()];
  return m ? (lang === "en" ? m[1] : m[0]) : key;
}
