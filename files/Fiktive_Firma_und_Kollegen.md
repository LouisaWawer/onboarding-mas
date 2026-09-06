# Fiktive Firma und Kolleg:innen

Grundlage für alle Inhalte in Chat, Intranet, Tickets und Kalender. Bewusst so gestaltet, dass sich unterschiedliche Testpersonen unabhängig von ihrem eigenen Berufsfeld hineinversetzen können (breite Screening-Zielgruppe: berufstätig oder in berufsbezogener Ausbildung).

## Die Firma

**Name**: Nordlicht Software GmbH
**Branche**: B2B-Software (Projekt- und Ressourcenplanung für mittelständische Unternehmen)
**Größe**: ca. 140 Mitarbeitende
**Standort**: Hamburg, hybrides Arbeiten üblich
**Ton/Kultur**: Modern, unaufgeregt, kollegial-informell (Duzkultur), technikaffin aber nicht abgehoben – passend zu einer glaubwürdigen Umgebung für den Einsatz eines KI-Onboarding-Assistenten

**Kurzbeschreibung** (für Intranet-Startseite): *"Nordlicht Software entwickelt Planungstools, mit denen mittelständische Unternehmen ihre Projekte und Teams einfacher organisieren. Wir sind ca. 140 Kolleg:innen, verteilt auf Produktentwicklung, Vertrieb, Customer Success und die üblichen Querschnittsfunktionen."*

**Rolle der neuen Mitarbeiter:in (Testperson)**: bewusst allgemein gehalten, keine tiefe Fachrolle – z.B. "neue:r Mitarbeiter:in im Projektteam" ohne Spezifizierung der genauen Abteilung. Das hält die Aufgaben (VPN, Kalender, organisatorische Fragen) für jede Testperson gleich nachvollziehbar, unabhängig vom eigenen Berufshintergrund.

## Kolleg:innen

⚠️ **Aktualisiert nach Figma-Stand** – abweichend von der ursprünglichen Planung, jetzt as-built:

| Name | Rolle | Auftrittsort | Avatar-Farbe (Figma) |
|---|---|---|---|
| **Max Vogel** | IT Support | Chat-DM, Tickets-Kontext | `avatar6` `#ae549c` |
| **Anna Schmidt** | HR Business Partnerin | Chat-DM, vermutlich Willkommensnachricht | `avatar4` `#561780` |
| **Laura Seifert** | Controlling | Chat, #allgemein (Kanalpräsenz) – rein atmosphärisch, keine Szenario-Funktion | `avatar2` `#a98cc4` |
| **Tom Bauer** | Vertrieb, **Buddy** | Chat, #allgemein, lädt zum Kaffee/Gruppenchat ein, Organisator des Kalender-Meetings (Aufgabe 3) | `avatar1` `#854595` |
| **Lars Becker** | Marketing | Chat, #allgemein (Kanalpräsenz) – rein atmosphärisch, keine Szenario-Funktion | `avatar-5` `#4a1c85` |

**Lumi (Onboarding-Assistent)**: siehe eigener Abschnitt unten – Avatar-Farbe `--color/assistant` `#5b6aec`.

**Onboarding-Assistent: Lumi** – geschlechtsneutraler Name, angelehnt an "Licht"/"Lumen" und damit an den Firmennamen "Nordlicht" (siehe auch das Aurora-Farbkonzept). Tritt als klar erkennbarer KI-Assistent auf (Transparenz-Prinzip, über das Funken-Symbol statt Initialen), erscheint aber in derselben Kontaktliste wie die menschlichen Kolleg:innen (siehe Chat-Wireframe) und wird von Nutzer:innen ähnlich adressiert wie eine Kollegin/ein Kollege.

**Visuelle Identität**: **Runder Avatar wie bei den menschlichen Kolleg:innen** (keine eigene Form mehr – frühere Idee eines abgerundeten Quadrats wurde verworfen), in Akzentfarbe `#5B6AEC`, mit einem Funken-/Sparkle-Symbol statt Initialen. Die Unterscheidung Mensch/Agent erfolgt **allein über das Icon**, nicht über die Form – bewusst dezenter als ursprünglich geplant. Als eigene Figma-Component (`Avatar/Lumi`) angelegt und konsistent überall verwendet, wo Lumi auftritt: Kontaktliste, Nachrichten-Bubbles, Gruppenchat-Einladung, Eskalations-Übergabe-Nachricht. Der animierte, leuchtende Ring (aus der Kugelbild-Inspiration) bleibt separat für den ambienten Statuspunkt reserviert – zwei Detailgrade, ein gemeinsames "Licht"-Thema.

## Verwendung in den Apps

- **Chat**: DMs von Anna Schmidt (HR, vermutlich Willkommen), Max Vogel (IT-Zugang/VPN-Hinweis), Tom Bauer (Kaffee-Einladung/Gruppenchat), Lumi/Onboarding-Assistent (durchgehend); #allgemein mit vereinzelten Nachrichten von Laura Seifert/Lars Becker
- **Intranet**: Team-Übersicht mit allen fünf Personen + Lumi (inkl. bewusst korrigierbarem/veraltetem Eintrag für die Override-Aufgabe, z.B. falsche Rolle oder falsches Team bei einer Person)
- **Tickets**: Max als Bearbeiter auf IT-Tickets, Anna als Bearbeiterin auf HR-Tickets
- **Kalender**: Tom als Organisator des Team-Meetings (Aufgabe 3 aus dem Szenario-Dokument)
