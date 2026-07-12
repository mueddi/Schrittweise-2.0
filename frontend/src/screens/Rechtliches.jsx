import { Link, useLocation } from "react-router-dom";

// Impressum & Datenschutzerklärung – öffentlich erreichbar, im Design-Look.

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

export function Impressum() {
  return (
    <Shell title="Impressum">
      <H>Betreiber</H>
      <P>
        Mahmmoud Said<br />
        St. Georgen-Strasse<br />
        9000 St.Gallen, Schweiz
      </P>
      <H>Kontakt</H>
      <P>
        E-Mail: <a href="mailto:mahmmouds62@gmail.com" style={{ color: "#4f46e5" }}>mahmmouds62@gmail.com</a>
      </P>
      <H>Verantwortlich für den Inhalt</H>
      <P>Mahmmoud Said</P>
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
        bearbeitet – gemäss dem Schweizer Datenschutzgesetz (revDSG). Stand: Juli 2026.
      </P>

      <H>1. Verantwortliche Stelle</H>
      <P>
        Mahmmoud Said, St. Georgen-Strasse, 9000 St.Gallen, Schweiz<br />
        E-Mail: <a href="mailto:mahmmouds62@gmail.com" style={{ color: "#4f46e5" }}>mahmmouds62@gmail.com</a>
      </P>

      <H>2. Welche Daten wir bearbeiten</H>
      <P>
        <b>Konto:</b> E-Mail-Adresse, ein Passwort (nur als kryptografischer Hash
        gespeichert) und ein frei wählbarer Anzeigename (bewusst kein Klarname nötig),
        optional die Klassenstufe.<br />
        <b>Lerninhalte:</b> eingegebene, fotografierte oder mit dem Stift geschriebene
        Aufgaben und der Chat-Verlauf mit dem Tutor.<br />
        <b>Lernfortschritt:</b> daraus berechnete grobe Aggregate (gelöste Aufgaben,
        Selbständigkeits-Quote, aktive Tage, Themen-Trends).<br />
        <b>Käufe:</b> bei einem Token-Kauf den Betrag und den Zeitpunkt der Gutschrift
        (keine Zahlungsdaten, siehe Ziffer 7).
      </P>

      <H>3. Wofür (Zweck)</H>
      <P>
        Ausschliesslich für den Betrieb des Lern-Tutors: Anmeldung mit E-Mail und
        Passwort (bei vergessenem Passwort per einmaligem E-Mail-Link), pädagogische
        Hinweise entlang der Hinweis-Leiter, Fortschrittsanzeige und – nur mit
        ausdrücklicher Freigabe – die aggregierte Elternansicht.
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
        Anthropic API (Anthropic PBC, USA) übermittelt. Auch hochgeladene Aufgabenfotos
        und Stift-Eingaben werden zur Erkennung des Geschriebenen an Anthropic
        übermittelt. Gemäss den API-Bedingungen von Anthropic werden diese Daten nicht
        zum Training von KI-Modellen verwendet.
      </P>

      <H>6. Hosting und Speicherort</H>
      <P>
        Die Anwendung läuft bei Vercel Inc. (USA); die Datenbank mit Konto- und
        Lerndaten liegt bei Supabase (Rechenzentrum in Frankfurt, EU). Ein Teil der
        Verarbeitung findet damit in den USA statt. Es gelten zusätzlich die
        Datenschutzbestimmungen dieser Anbieter.
      </P>

      <H>7. Zahlungsabwicklung</H>
      <P>
        Token-Käufe werden über Stripe Payments Europe Ltd. abgewickelt. Karten- oder
        TWINT-Daten werden direkt von Stripe verarbeitet und erreichen unsere Server
        nie; wir speichern nur den Betrag und den Zeitpunkt der Gutschrift.
        Minderjährige benötigen für Käufe das Einverständnis ihrer
        Erziehungsberechtigten.
      </P>

      <H>8. Aufbewahrung &amp; Löschung</H>
      <P>
        Konto- und Lerndaten bleiben gespeichert, solange das Konto besteht. Auf Anfrage
        an die oben genannte Adresse löschen wir ein Konto samt aller zugehörigen Daten
        vollständig. E-Mail-Login-Links (Passwort vergessen) sind 30 Minuten gültig und
        einmalig verwendbar.
      </P>

      <H>9. Deine Rechte</H>
      <P>
        Auskunft, Berichtigung, Löschung und Datenherausgabe – Anfrage genügt per E-Mail
        an die verantwortliche Stelle. Bei Minderjährigen können die
        Erziehungsberechtigten diese Rechte ausüben.
      </P>

      <H>10. Keine Werbung, kein Tracking</H>
      <P>
        Schrittweise setzt keine Werbe- oder Tracking-Cookies ein. Es wird nur ein
        technisch notwendiges Login-Token im Browser gespeichert.
      </P>
    </Shell>
  );
}

export function Agb() {
  return (
    <Shell title="AGB">
      <P>
        Allgemeine Geschäftsbedingungen für die Nutzung von Schrittweise, betrieben von
        Mahmmoud Said, St. Georgen-Strasse, 9000 St.Gallen, Schweiz
        (<a href="mailto:mahmmouds62@gmail.com" style={{ color: "#4f46e5" }}>mahmmouds62@gmail.com</a>).
        Stand: Juli 2026.
      </P>

      <H>1. Leistung</H>
      <P>
        Schrittweise ist ein KI-gestützter Mathe-Lern-Tutor für die Oberstufe. Jedes
        Konto erhält 50 Gratis-Tokens pro Kalendermonat. Zusätzlich können einmalige
        Token-Pakete gekauft werden. 1 Token entspricht 1 Rappen KI-Leistung: Jede
        Tutor-Antwort bucht Tokens entsprechend ihrem Rechenaufwand ab – eine normale
        Antwort kostet in der Regel 1 Token, eine Antwort mit Foto-Auswertung oder
        aufwändiger Geometrie ca. 3–5 Tokens. Auch die Handschrift-/Foto-Erkennung
        beim Erfassen einer Aufgabe wird so abgerechnet. Tokens sind kein Abo,
        verlängern sich nicht automatisch und laufen nicht ab.
      </P>

      <H>2. Preise</H>
      <P>
        Schnupper-Paket: CHF 2.– (200 Tokens) · Starter-Paket: CHF 9.– (900 Tokens) ·
        Power-Paket: CHF 19.– (1900 Tokens). Alle Preise in Schweizer Franken, einmalig.
      </P>

      <H>3. Zahlung</H>
      <P>
        Die Zahlung erfolgt über Stripe (Karte oder TWINT). Die Tokens werden nach
        Zahlungseingang automatisch dem Konto gutgeschrieben – in der Regel innert
        Sekunden.
      </P>

      <H>4. Minderjährige</H>
      <P>
        Für Käufe durch Minderjährige ist das Einverständnis der Erziehungsberechtigten
        erforderlich. Mit dem Kauf bestätigst du, dass dieses Einverständnis vorliegt.
      </P>

      <H>5. Rückerstattung</H>
      <P>
        Ungenutzte Tokens können innert 14 Tagen nach dem Kauf per E-Mail an die oben
        genannte Adresse zurückgegeben werden (anteilige Rückerstattung). Für bereits
        verbrauchte Tokens ist die Leistung erbracht – dafür gibt es keine Rückerstattung.
      </P>

      <H>6. Verfügbarkeit und Gewähr</H>
      <P>
        Schrittweise ist ein Lernwerkzeug und ersetzt keinen Unterricht. KI-generierte
        Hinweise können im Einzelfall fehlerhaft sein; dafür wird keine Gewähr
        übernommen. Eine ununterbrochene Verfügbarkeit wird angestrebt, aber nicht
        garantiert. Bei längeren Ausfällen werden betroffene Tokens auf Anfrage ersetzt.
      </P>

      <H>7. Konto und Missbrauch</H>
      <P>
        Pro Person ein Konto. Bei Missbrauch (z.B. automatisierte Anfragen,
        Weiterverkauf von Zugängen) kann das Konto gesperrt werden.
      </P>

      <H>8. Anwendbares Recht</H>
      <P>
        Es gilt Schweizer Recht. Gerichtsstand ist St.Gallen, zwingende gesetzliche
        Gerichtsstände bleiben vorbehalten.
      </P>
    </Shell>
  );
}

export default function Rechtliches() {
  const { pathname } = useLocation();
  if (pathname.includes("agb")) return <Agb />;
  return pathname.includes("datenschutz") ? <Datenschutz /> : <Impressum />;
}
