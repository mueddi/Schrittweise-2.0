import { Link, useLocation } from "react-router-dom";

// Impressum & Datenschutzerklärung – öffentlich erreichbar, im Design-Look.
// Platzhalter [BITTE ERGÄNZEN] vor dem Launch mit echten Betreiber-Angaben füllen.

function Shell({ title, children }) {
  return (
    <div style={{ minHeight: "100vh", background: "#fbfbfd" }}>
      <nav style={{ display: "flex", alignItems: "center", gap: 10, padding: "20px 40px", maxWidth: 860, margin: "0 auto" }}>
        <Link to="/" style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ width: 26, height: 26, borderRadius: 8, background: "#6366f1" }} />
          <span style={{ fontWeight: 800, fontSize: 19, color: "#4f46e5", letterSpacing: "-.02em" }}>Schrittweise</span>
        </Link>
        <Link to="/" style={{ marginLeft: "auto", fontSize: 13, fontWeight: 600, color: "#4f46e5" }}>← zur Startseite</Link>
      </nav>
      <div style={{ maxWidth: 760, margin: "0 auto", padding: "16px 40px 80px" }}>
        <h1 style={{ fontSize: 32, fontWeight: 900, letterSpacing: "-.03em", marginBottom: 24 }}>{title}</h1>
        <div style={{ background: "#fff", border: "1px solid #e7e8ee", borderRadius: 18, padding: "28px 32px", fontSize: 14.5, lineHeight: 1.65, color: "#1a1c22" }}>
          {children}
        </div>
      </div>
    </div>
  );
}

const H = ({ children }) => <h2 style={{ fontSize: 17, fontWeight: 800, margin: "26px 0 8px", letterSpacing: "-.01em" }}>{children}</h2>;
const P = ({ children }) => <p style={{ margin: "0 0 12px", color: "#3a3d46" }}>{children}</p>;
const Todo = ({ children }) => (
  <span style={{ background: "#fdf3e6", color: "#a05c12", borderRadius: 6, padding: "1px 6px", fontWeight: 600 }}>{children}</span>
);

export function Impressum() {
  return (
    <Shell title="Impressum">
      <H>Betreiber</H>
      <P>
        <Todo>[BITTE ERGÄNZEN: Name / Firma]</Todo><br />
        <Todo>[Strasse Nr.]</Todo><br />
        <Todo>[PLZ Ort, Schweiz]</Todo>
      </P>
      <H>Kontakt</H>
      <P>
        E-Mail: <Todo>[kontakt@deine-domain.ch]</Todo>
      </P>
      <H>Verantwortlich für den Inhalt</H>
      <P><Todo>[Name der verantwortlichen Person]</Todo></P>
      <H>Haftungsausschluss</H>
      <P>
        Schrittweise ist ein Lernwerkzeug und ersetzt keinen Unterricht. Trotz sorgfältiger
        Prüfung übernehmen wir keine Gewähr für die fachliche Richtigkeit einzelner
        KI-generierter Hinweise. Für Inhalte externer Links sind ausschliesslich deren
        Betreiber verantwortlich.
      </P>
    </Shell>
  );
}

export function Datenschutz() {
  return (
    <Shell title="Datenschutzerklärung">
      <P>
        Diese Datenschutzerklärung informiert darüber, welche Personendaten Schrittweise
        bearbeitet – gemäss dem Schweizer Datenschutzgesetz (revDSG).{" "}
        <Todo>[Vor dem Launch juristisch prüfen lassen und Betreiber-Angaben ergänzen.]</Todo>
      </P>

      <H>1. Verantwortliche Stelle</H>
      <P><Todo>[Name / Firma, Adresse, E-Mail – wie im Impressum]</Todo></P>

      <H>2. Welche Daten wir bearbeiten</H>
      <P>
        <b>Konto:</b> E-Mail-Adresse und ein frei wählbarer Anzeigename (bewusst kein
        Klarname nötig), optional die Klassenstufe.<br />
        <b>Lerninhalte:</b> eingegebene oder fotografierte Aufgaben und der Chat-Verlauf
        mit dem Tutor.<br />
        <b>Lernfortschritt:</b> daraus berechnete grobe Aggregate (gelöste Aufgaben,
        Selbständigkeits-Quote, aktive Tage, Themen-Trends).
      </P>

      <H>3. Wofür (Zweck)</H>
      <P>
        Ausschliesslich für den Betrieb des Lern-Tutors: Anmeldung per Login-Link,
        pädagogische Hinweise entlang der Hinweis-Leiter, Fortschrittsanzeige und – nur
        mit ausdrücklicher Freigabe – die aggregierte Elternansicht.
      </P>

      <H>4. Privacy by Design: Was Eltern sehen (und was nicht)</H>
      <P>
        Verknüpfte Eltern sehen ausschliesslich grobe Wochen-Aggregate. Chat-Nachrichten
        sind für Eltern technisch nicht abrufbar; die Aggregate liegen in einer separaten
        Datenbank-Tabelle. Die Freigabe kann in den Einstellungen jederzeit widerrufen werden.
      </P>

      <H>5. KI-Verarbeitung (Auftragsbearbeiter)</H>
      <P>
        Zur Erzeugung der Tutor-Antworten werden Aufgabentext und Chat-Verlauf an die
        Anthropic API (Anthropic PBC, USA) übermittelt. Gemäss den API-Bedingungen von
        Anthropic werden diese Daten nicht zum Training von Modellen verwendet.
        Hochgeladene Aufgabenfotos werden auf unserem Server erkannt (OCR) und nicht an
        Dritte weitergegeben.
      </P>

      <H>6. Hosting</H>
      <P>
        Die Anwendung wird bei <Todo>[Hosting-Anbieter + Region eintragen, z.B. Render
        (Region Frankfurt/EU)]</Todo> betrieben. Es gelten zusätzlich dessen
        Datenschutzbestimmungen.
      </P>

      <H>7. Aufbewahrung & Löschung</H>
      <P>
        Konto- und Lerndaten bleiben gespeichert, solange das Konto besteht. Auf Anfrage
        an die oben genannte Adresse löschen wir ein Konto samt aller zugehörigen Daten
        vollständig. Login-Links sind 30 Minuten gültig und einmalig verwendbar.
      </P>

      <H>8. Deine Rechte</H>
      <P>
        Auskunft, Berichtigung, Löschung und Datenherausgabe – Anfrage genügt per E-Mail
        an die verantwortliche Stelle. Bei Minderjährigen können die
        Erziehungsberechtigten diese Rechte ausüben.
      </P>

      <H>9. Keine Werbung, kein Tracking</H>
      <P>
        Schrittweise setzt keine Werbe- oder Tracking-Cookies ein. Es wird nur ein
        technisch notwendiges Login-Token im Browser gespeichert.
      </P>
    </Shell>
  );
}

export default function Rechtliches() {
  const { pathname } = useLocation();
  return pathname.includes("datenschutz") ? <Datenschutz /> : <Impressum />;
}
