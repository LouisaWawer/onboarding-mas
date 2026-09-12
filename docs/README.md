# README – Dokumentation Onboarding-MAS-Prototyp

Zentraler Einstiegspunkt für alle Dokumente zum Prototyp. Diese Datei erklärt, was wo steht, in welcher Reihenfolge sie sich zu lesen lohnen, und was der aktuelle Projektstand ist.

## Aktueller Stand (zusammengefasst)

**Design (Figma)**: Alle fünf Sandbox-Screens (Chat, Intranet, Knowledge Hub, Tickets, Kalender) sind entworfen, inklusive Komponenten-Bibliothek (Sidebar-Icons, Avatar/Status, Chat-Elemente, Tree-Navigation, Tabellen). Farbsystem, Kolleg:innen-Cast und Inhalte sind zwischen Figma und Dokumentation synchronisiert.

**Code (sandbox-app)**: Mit Claude Code umgesetzt, auf Basis der Figma-Datei. Sidebar, Chat, Tickets-Tabelle, Avatar/Status-System mit funktionierendem Layout stehen.

**Backend (LangGraph/Agent)**: Deutlich weiter als ursprünglich geplant – nicht mehr bis nach der Interviewauswertung zurückgestellt. Funktionierender, mehrfach getesteter Graph: Supervisor (Zerlegung + Routing per Tool Use, vier Kategorien inkl. `scheduling`), Infrastructure-/Info-/Scheduling-Agent, Prüfer (mit Entwurfs-/Freigabe-Mechanismus), zweistufiger Kontext-Check (vor UND nach der ersten Bestätigung), `interrupt()`-basierte Bestätigung (abhängig von Kontrollgrad UND Kritikalität), Eskalation mit echten Kolleg:innen-Verweisen. FastAPI-Schicht (`backend/api/`) ist gebaut und getestet (19 grüne Tests, `test_api_manual.py`): Sessions, Anfragen, SSE-Event-Stream, Rationale-Spiegel, mehrbenutzerfähig, inkl. der sechs Statuspunkt-Werte (idle/working/waiting/result/error/suggestion). Details siehe `Setup_Dokumentation.md`, Abschnitt 2/7. Noch offen: die `sandbox-app` selbst ruft diese Endpunkte noch nicht auf (Frontend-Anbindung, siehe Abschnitt 8).

**Tauri-Shell**: Projekt-Grundgerüst existiert und ist end-to-end mit dem Backend verbunden (bestätigter Ping-Test, siehe `Setup_Dokumentation.md` Abschnitt 4/5). Die Tauri-Shell ist laut Konzept (ADR-003) die native App-Hülle, die die Sandbox-App als Frontend lädt – Statuspunkt und Bestätigungs-/Interrupt-Anzeige sind demnach Bestandteile bzw. ein Overlay INNERHALB der geladenen Sandbox-App, kein separates System neben ihr. Noch nicht begonnen: das eigentliche Laden der Sandbox-App in der Shell sowie die Statuspunkt-UI selbst und die Bestätigungskarte/Interrupt-Anzeige. Backend-seitig fertig sind die sechs Statuswerte und die Rive-Dateien liegen vor – im Frontend existiert davon aber noch nichts, die Sandbox-App hat bis heute keinen einzigen Aufruf an die FastAPI-Schicht (siehe `Setup_Dokumentation.md` Abschnitt 4/8).

**Nutzerstudie**: Szenario, Aufgaben und Erhebungsmethodik sind konzipiert, Testskript im Detail steht noch aus.

## Die Dokumente im Überblick

Empfohlene Lesereihenfolge, falls du (oder jemand anderes) sich neu einarbeitet:

### 1. Für den Gesamtüberblick

**`README.md`** (diese Datei) – Startpunkt, Status, Struktur.

**`Projekt_Vorlagen_Prototyp.md`** – PRD-Kurzform (Ziel, Anforderungen, Nicht-Ziele), Architecture Decision Records (ADR-001 bis 004: Agentenframework, Screen-Kontext ohne Screen-Capture, Tauri als App-Hülle, Guardrail-Strategie), Risiko-Register (inkl. tatsächlich aufgetretener Risiken wie macOS-Berechtigungsprobleme und Doku/Code-Drift).

### 2. Für die inhaltliche/konzeptionelle Seite

**`Fiktive_Firma_und_Kollegen.md`** – Die fiktive Firma "Nordlicht Software GmbH", der Kolleg:innen-Cast (Max Vogel/IT, Anna Schmidt/HR, Tom Bauer/Vertrieb+Buddy, Laura Seifert/Controlling, Lars Becker/Marketing), Lumi (Name, visuelle Identität), Avatar-Zuordnung.

**`Szenario_Interaktionsdesign.md`** – Sandbox-Struktur (5 Apps), Interaktions-Oberflächen (DM, Screen-Viewer, vereinfachte Gruppenchat/Kanal-Varianten), Knowledge-Hub-Suchverhalten, Studiendesign (qualitativ, eine Variante), narrativer Aufgabenbogen, Erhebungsmethodik.

### 3. Für die visuelle/inhaltliche Umsetzung

**`Finale_Farbpalette.md`** – Alle Farbwerte (Neutraltöne, Statusfarben, Akzent, Avatarfarben), als Hex-Tabelle und fertige CSS-Variablen. Mit Figma synchronisiert und verifiziert (nicht nur geschätzt).

**`Knowledge_Hub_Inhalte.md`** – Vollständige Wissensartikel-Texte (z.B. "Urlaub beantragen").

**`Intranet_Inhalte.md`** – Ankündigungs-/Blog-Beiträge für den Intranet-Bereich.

### 4. Für die technische Umsetzung

**`Setup_Dokumentation.md`** – Entwicklungsumgebung, Projektstruktur, Backend-/Sandbox-App-/Tauri-Setup, Logging-Architektur (strukturelle Kategorisierung von Agent-Interaktionen), offene nächste Schritte.

**`CODE_UEBERSICHT.md`** – Komponenten-Nachschlagewerk, gegen den tatsächlichen Code-Stand verifiziert (Verifikationsdatum in der Datei selbst) – kein Entwurf mehr, sollte aber weiterhin vor größeren Sandbox-App-Änderungen gegengeprüft werden (siehe Pflegehinweis unten).

## Pflegehinweis

Diese Dokumentation hat sich als anfällig dafür erwiesen, vom tatsächlichen Figma-/Code-Stand abzuweichen (siehe Risiko R07 im Risiko-Register) – mehrfach mussten Namen, Farbwerte oder Statuslogik nachträglich korrigiert werden. Praxis, die sich bewährt hat: **vor größeren neuen Bauschritten kurz gegenprüfen**, ob Doku und Figma/Code noch übereinstimmen, statt das erst am Ende der Arbeit zu bemerken.

## Was als Nächstes ansteht

Siehe „Offene nächste Schritte" in `Setup_Dokumentation.md` (Abschnitt 8) für die vollständige Liste. Backend (Korrekturschleife, Test-Hook-Entfernung, `scheduling_agent`, FastAPI-Schicht, alle fünf Sandbox-Screens im Code) ist inzwischen fertig und getestet. Größte offene Blöcke:
1. Sandbox-App an die FastAPI-Schicht anbinden (Chat, Panel, Statuspunkt, Bestätigungskarte, Transparenzblock, Anfragen-Liste) – das Backend selbst ist fertig, das Frontend ruft es noch nicht auf
2. Tauri-Shell: Sandbox-App tatsächlich als Frontend laden, Statuspunkt-UI (Zustandswechsel, Rive) und Bestätigungskarte/Interrupt-Anzeige bauen – siehe `Setup_Dokumentation.md` Abschnitt 4 für den genauen Stand
3. Testskript final ausformulieren
4. Pilot-Test / Red-Teaming vor der eigentlichen Studie
