# Szenario- und Interaktionsdesign

Ergänzt die Setup-Dokumentation um die inhaltlichen/konzeptionellen Entscheidungen zu Sandbox-Struktur, Interaktions-Oberflächen und Testszenarien.

## 1. Sandbox-Struktur

Fünf Apps in der Seitenleiste (Teams/Slack-Stil, keine E-Mail – nur interne Kommunikation). Intranet und Knowledge Hub sind bewusst **getrennte Icons**, nicht Tabs innerhalb eines Bereichs – Grund: Auffindbarkeit während der Studie darf kein Störfaktor sein (siehe Entscheidung weiter unten im Chat-Verlauf, kein "versteckter Tab").

| App | Inhalt |
|---|---|
| **Chat** | Kanäle (#allgemein) + Direktnachrichten (Max/IT, Anna/HR, Tom/Buddy+Vertrieb, Laura/Controlling, Lars/Marketing, **Lumi** als gleichwertiger Kontakt) |
| **Intranet** | Allgemeine, unpersonalisierte Unternehmensinhalte: Ankündigungen (Blog-Format), Mitarbeitendenverzeichnis, Neu im Team, Über uns – bewusst **kein** personalisierter Ort |
| **Knowledge Hub** | Durchsuchbare Wissensdatenbank mit Baumstruktur (z.B. HR/Abwesenheit/Urlaub/Urlaub beantragen), "Frag Lumi"-Suche (liefert Inhalte, keine Konversation), proaktive Lumi-Vorschläge mit Begründung |
| **Tickets** | Bestehende Tickets + Formular für neue Anfragen (u.a. VPN-Zugang) |
| **Kalender** | Terminübersicht, Möglichkeit Meetings einzutragen |

Externe Kommunikation (E-Mail) ist für das Szenario nicht relevant und wird nicht simuliert.

Die Onboarding-Checkliste ist **nicht** Teil des Intranets (da unpersonalisiert) – sie gehört stattdessen in den Chat-Bereich, verknüpft mit Lumi (z.B. als anheftbare Fortschritts-Karte im Gesprächsverlauf).

## 2. Interaktions-Oberflächen des Agenten

Wichtige architektonische Vereinfachung: Die verschiedenen "Modi" sind keine unabhängigen Systeme, sondern Kombinationen aus **Oberfläche** (wo sichtbar) und **Autonomiegrad** (wie der Agent agiert – identisch mit dem K-Faktor aus der Vignetten-Studie). Eine Kernagentenlogik, mehrere Auslieferungsorte.

### Voll funktionsfähig (für die Nutzerstudie)

| Oberfläche | Beschreibung |
|---|---|
| **Direkte DM mit Agent** | Vollständige Konversation im Chat-Tool, identisch zugänglich über das Panel des peripheren Statuspunkts (gemeinsamer Konversationsstand, zwei Zugänge) |
| **Screen-Viewer-Overlay** | Agent hat Zugriff auf aktuellen Sandbox-Zustand während einer Aufgabe, kann proaktiv unterstützen oder auf Zwischenfragen reagieren |

### Vereinfacht / gescriptet (nicht voll funktionsfähig)

| Oberfläche | Umsetzung |
|---|---|
| **Gruppenchat mit Kolleg:innen** | Feste, vorgeschriebene Kolleg:innen-Nachrichten statt vollständiger Multi-User-Simulation; Agent kann eingeladen werden und reagiert im selben Kanal |
| **Öffentlicher Kanal (#allgemein)** | Agent kann eine Nachricht sichtbar posten (z.B. Willkommensgruß), aber ohne volle interaktive Konversationslogik an dieser Stelle |

*Begründung*: Für die Kernforschungsfrage (Transparenz/Kontrolle in der 1:1-Interaktion) sind DM und Screen-Viewer entscheidend. Gruppenchat/Kanal demonstrieren die soziale Dimension des Konzepts, ohne dass dafür vollständige Multi-Agenten-Konversationslogik nötig ist – im Ausblick (Kap. 6.2) als Erweiterungspotenzial benennen.

## 3. Autonomiegrad = Wiederverwendung des K-Faktors

Der "autonome Hintergrundmodus" ist keine separate Funktion, sondern K– (aus der 3×3-Vignette) angewendet auf eine reale Aufgabe: Agent arbeitet selbstständig, meldet nur bei unternehmensweit kritischen/unsicheren Fällen. K+/K0 entsprechen den interaktiveren, bestätigungsreicheren Varianten. Dieselbe Logik, die für die Prototyp-Varianten (viel/wenig Kontrolle) gebaut wird, erzeugt also automatisch auch den Eindruck unterschiedlicher "Modi".

## 4. Eskalation als Ereignis, nicht als Modus

Eskalation/Übergabe an eine echte Person ist ein zusätzlicher Zweig im LangGraph, der aus jeder Oberfläche heraus erreichbar ist (z.B. bei Themen außerhalb der Zuständigkeit des Agenten, wie Gehaltsfragen). Kein eigenständiges System.

## 5. Finale Aufgabentabelle für die Nutzerstudie

| # | Aufgabe | Abgedeckte Fähigkeit | Trigger | Oberfläche(n) | Schritt (Abschnitt 8) |
|---|---|---|---|---|---|
| 1 | VPN-Zugang einrichten | Zugänge (aus Vignetten-Basisszenario) | hohe Kritikalität: Verhalten der konfigurierten Kontrollstufe | DM oder Statuspunkt-Panel | 2 |
| 2 | Team-Meeting im Kalender eintragen | Kalender (aus Vignetten-Basisszenario) | niedrigere Kritikalität als Kontrast (zu Aufgabe 1): Verhalten der konfigurierten Kontrollstufe | DM oder Statuspunkt-Panel | 3 |
| 3 | Offene organisatorische Frage stellen | Organisatorische Fragen (aus Vignetten-Basisszenario) | Mehrdeutigkeit: Verhalten der konfigurierten Transparenzstufe | DM oder Statuspunkt-Panel | 4 |
| 4 | Mehrstufigen Prozess peripher verfolgen | – | Calm-Tech/Statuspunkt, kein T/K-Trigger | Statuspunkt (peripher) | 5 |
| 5 | Fehlerhaften Agentenvorschlag korrigieren | – | Override/Eingriffsmöglichkeit | DM oder Screen-Viewer | 6 |
| 6 (optional) | Screen-Viewer aktiv nutzen während einer Aufgabe | – | Kontextuelle Unterstützung | Screen-Viewer-Overlay | durchgängig verfügbar (Schritt 2–6), kein eigener Schritt |

## 6. Schreibunterstützung im Chat-Composer

Zusätzliche Agenten-Fähigkeit, kein eigener Modus: Beim Verfassen von Nachrichten an Kolleg:innen (HR, IT, Buddy, Gruppenchat) steht ein kleiner Button im Eingabefeld zur Verfügung ("Vorschlag"), der auf Anfrage einen Formulierungsvorschlag liefert – bewusst **nicht** automatisch als Ghost-Text während des Tippens, um dem Prinzip "keine ungefragte Einmischung" (Calm Technology, situative Kontrolle) treu zu bleiben.

**Technisch**: kein separates System, sondern ein zusätzliches Tool desselben Agenten – Klick sendet Empfänger-Kontext ans Backend, Vorschlag wird zum Übernehmen/Bearbeiten/Verwerfen angezeigt.

**Einordnung im Testskript**: kein eigener Aufgabenblock, sondern optional während bestehender Aufgaben (v.a. Schritt 4, organisatorische Fragen) verfügbar – Nutzung wird beiläufig beobachtet/geloggt.

## 7. Studiendesign der Prototyp-Nutzerstudie

Im Unterschied zur quantitativen Vignetten-Studie (3×3, zwischen Bedingungen vergleichend) wird für den Prototyp **eine** ausgereifte Variante gebaut und **qualitativ** evaluiert (Think-Aloud + semi-strukturiertes Interview). Fokus: Aufbau mentaler Modelle über die Zeit (RQ1), erlebte Transparenz/Kontrolle in echter Interaktion (RQ2/RQ3) – als komplementäre, tiefere Perspektive zu den quantitativen Befunden, nicht als weiterer Gruppenvergleich. Das reduziert den Implementierungsaufwand auf eine einzige, funktionsfähige Prototyp-Version statt mehrerer Feature-Flag-Varianten.

## 8. Ablauf und Aufgabenreihenfolge (narrativer Bogen)

Feste Reihenfolge statt Randomisierung – der Lerneffekt über den Verlauf ist hier erwünschter Untersuchungsgegenstand (RQ1), kein zu kontrollierender Störfaktor.

| Schritt | Inhalt | Testet |
|---|---|---|
| 0 – Briefing | "Erster Arbeitstag"-Vignette (angelehnt an Basis-Szenario der quantitativen Studie), Hinweis auf simulierte Umgebung, Think-Aloud-Anleitung | – |
| 1 | Willkommensnachricht des Agenten (DM), erwähnt beiläufig den Team-Kanal | inzidentelle Entdeckung von Kanal/Gruppenchat |
| 2 | VPN-Zugang einrichten | K-Unterschied, hohe Kritikalität |
| 3 | Meeting im Kalender eintragen | K-Unterschied, niedrigere Kritikalität (Kontrast zu Schritt 2) |
| 4 | Zwei organisatorische Fragen stellen – eine im Zuständigkeitsbereich des Agenten, eine bewusst außerhalb (z.B. Gehaltsfrage) | T-Unterschied bei Mehrdeutigkeit + Eskalations-Zweig (statt eigener Aufgabe) |
| 5 | Mehrstufigen Hintergrundprozess peripher verfolgen (Statuspunkt) | Calm-Tech-Prinzip |
| 6 | Fehlerhaften Agentenvorschlag korrigieren | Override/Kontrolleingriff |

Screen-Viewer-Overlay und Schreibunterstützung sind keine eigenen Schritte, sondern während Schritt 2–6 durchgängig verfügbare Fähigkeiten – ihre (Nicht-)Nutzung wird beiläufig beobachtet/geloggt.

## 9. Erhebungsmethodik

- **Think-Aloud durchgehend**: "Was erwartest du, dass der Agent jetzt tut?" an kritischen Momenten (v.a. vor Interrupt-Punkten)
- **Kurze Zwischenfragen** nach besonders aufschlussreichen Momenten (z.B. direkt nach der Eskalation, nach dem Fehler in Schritt 6)
- **Abschließendes semi-strukturiertes Interview**: mentale Modelle (RQ1), Eindruck von Transparenz/Kontrolle in echter Nutzung (RQ2/RQ3), Vergleich zum Alltagsverständnis von Apps/Kolleg:innen
- Anker-Items aus der quantitativen Studie (z.B. "Ich vertraue darauf, dass das System in meinem Sinne handelt") können als Gesprächsimpulse im Interview dienen, nicht als Skalen-Score – dient der Trianguliation, nicht dem statistischen Vergleich

## 10. Knowledge-Hub-Suche: Inhaltsabruf statt Konversation

Die "Frag Lumi"-Suche im Knowledge Hub ist bewusst **kein** Mini-Chat und löst keine Konversation aus:

- **Normalfall**: Eingabe filtert/sortiert die vorhandene Artikelliste passend zur Frage – Lumi stellt Inhalte bereit, führt aber kein Gespräch. Kein Navigations-Zwang, keine Chat-Antwort direkt im Knowledge Hub.
- **Problemfall** (keine passenden Inhalte, Frage zu vage/außerhalb des Wissensbestands): Statt einer unbefriedigenden Notlösung im Suchfeld wird der **periphere Statuspunkt aktiv** – ein dezentes Signal, dass Lumi mehr dazu sagen könnte. Die Testperson entscheidet selbst, ob sie das Chat-Panel öffnet, kein erzwungener Sprung.

Technisch weiterhin **eine** zugrundeliegende Konversation/ein State (wie bei DM und Statuspunkt-Panel), aber die Knowledge-Hub-Suche selbst zeigt keine Chat-Bubble – nur der Status des peripheren Punkts ändert sich als Brücke zur eigentlichen Konversation.

## 11. Offene Punkte

- [ ] Konkrete Formulierungen für Chat-Nachrichten (HR/IT/Buddy/Agent) – nach Interviewauswertung final
- [ ] Wortlaut der Eskalations-Nachricht
- [ ] Entscheidung, ob Kanal-Post (#allgemein) fest im Szenario vorkommt oder nur optional erreichbar ist
- [ ] Logging: Kanalwahl pro Aufgabe mit erfassen (DM vs. Statuspunkt-Panel), liefert Zusatzdaten für RQ1
