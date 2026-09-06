# README – Dokumentation Onboarding-MAS-Prototyp

Zentraler Einstiegspunkt für alle Dokumente zum Prototyp. Diese Datei erklärt, was wo steht, in welcher Reihenfolge sie sich zu lesen lohnen, und was der aktuelle Projektstand ist.

## Aktueller Stand (zusammengefasst)

**Design (Figma)**: Alle fünf Sandbox-Screens (Chat, Intranet, Knowledge Hub, Tickets, Kalender) sind entworfen, inklusive Komponenten-Bibliothek (Sidebar-Icons, Avatar/Status, Chat-Elemente, Tree-Navigation, Tabellen). Farbsystem, Kolleg:innen-Cast und Inhalte sind zwischen Figma und Dokumentation synchronisiert.

**Code (sandbox-app)**: Wird aktuell mit Claude Code umgesetzt, auf Basis der Figma-Datei. Sidebar, Chat, Tickets-Tabelle, Avatar/Status-System stehen bereits mit funktionierendem Layout; weitere Screens folgen iterativ. Technische Muster (Layout, Icon-Handling) sind in `CODE_UEBERSICHT.md` festgehalten.

**Backend (LangGraph/Agent)**: Bewusst zurückgestellt bis nach der Interviewauswertung – noch nicht begonnen.

**Tauri-Shell (Statuspunkt + Interrupt-Overlay)**: Noch nicht begonnen, separates System von der Sandbox-App.

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
1. Verbleibende Sandbox-Screens fertigstellen (Code)
2. LangGraph-Backend nach Interviewauswertung
3. Tauri-Shell (Statuspunkt, Interrupt-Overlay)
4. Testskript final ausformulieren
5. Pilot-Test / Red-Teaming vor der eigentlichen Studie
