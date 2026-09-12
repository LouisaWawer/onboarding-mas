# README – Dokumentation Onboarding-MAS-Prototyp

Zentraler Einstiegspunkt für alle Dokumente zum Prototyp. Diese Datei erklärt, was wo steht, in welcher Reihenfolge sie sich zu lesen lohnen, und was der aktuelle Projektstand ist.

## Aktueller Stand (zusammengefasst)

**Design (Figma)**: Alle fünf Sandbox-Screens (Chat, Intranet, Knowledge Hub, Tickets, Kalender) sind entworfen, inklusive Komponenten-Bibliothek (Sidebar-Icons, Avatar/Status, Chat-Elemente, Tree-Navigation, Tabellen). Farbsystem, Kolleg:innen-Cast und Inhalte sind zwischen Figma und Dokumentation synchronisiert.

**Code (sandbox-app)**: Mit Claude Code umgesetzt, auf Basis der Figma-Datei. Sidebar, Chat, Tickets-Tabelle, Avatar/Status-System mit funktionierendem Layout stehen.

**Backend (LangGraph/Agent)**: Deutlich weiter als ursprünglich geplant – nicht mehr bis nach der Interviewauswertung zurückgestellt. Funktionierender, mehrfach getesteter Graph: Supervisor (Zerlegung + Routing per Tool Use), Infrastructure-Agent, Info-Agent (mit Dokumentensuche + Quellenangabe), Prüfer (mit Entwurfs-/Freigabe-Mechanismus), Kontext-Check, `interrupt()`-basierte Bestätigung, Eskalation mit echten Kolleg:innen-Verweisen. Details siehe `Setup_Dokumentation.md`, Abschnitt 2. Noch offen: `scheduling_agent`, FastAPI-Anbindung an die echte Sandbox-UI, finaler Test der Korrekturschleife (Test-Hook noch im Code).

**Tauri-Shell**: Projekt-Grundgerüst existiert und ist end-to-end mit dem Backend verbunden (bestätigter Ping-Test, siehe `Setup_Dokumentation.md` Abschnitt 4/5). Die eigentlichen Features – **Statuspunkt (Zustandswechsel) und Interrupt-Overlay** – sind noch nicht begonnen, separates System von der Sandbox-App.

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

**`CODE_UEBERSICHT.md`** – Komponenten-Nachschlagewerk (Start, muss laufend mit dem echten Code-Stand abgeglichen werden).

## Pflegehinweis

Diese Dokumentation hat sich als anfällig dafür erwiesen, vom tatsächlichen Figma-/Code-Stand abzuweichen (siehe Risiko R07 im Risiko-Register) – mehrfach mussten Namen, Farbwerte oder Statuslogik nachträglich korrigiert werden. Praxis, die sich bewährt hat: **vor größeren neuen Bauschritten kurz gegenprüfen**, ob Doku und Figma/Code noch übereinstimmen, statt das erst am Ende der Arbeit zu bemerken.

## Was als Nächstes ansteht

Siehe „Offene nächste Schritte" in `Setup_Dokumentation.md` für die vollständige Liste. Größte offene Blöcke:
1. Backend fertig testen (Korrekturschleife, Kontext-Check "geändert"-Fall), Test-Hook entfernen
2. `scheduling_agent` ergänzen, FastAPI-Anbindung an die echte Sandbox-UI
3. Verbleibende Sandbox-Screens fertigstellen (Code)
4. Tauri-Shell (Statuspunkt, Interrupt-Overlay)
5. Testskript final ausformulieren
6. Pilot-Test / Red-Teaming vor der eigentlichen Studie
