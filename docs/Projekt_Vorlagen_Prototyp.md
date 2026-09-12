# Vorlagen für die Prototyp-Dokumentation

Drei kompakte Dokumente, angelehnt an professionelle Praxis, aber auf BA-Rahmen zugeschnitten. Jede Vorlage enthält zuerst die leere Struktur, danach ein ausgefülltes Beispiel auf Basis der bisherigen Projektentscheidungen als Orientierung.

---

## 1. PRD-Kurzform (Product Requirements Document)

### Vorlage

```
Projektname:
Datum:
Version:

1. Problem & Ziel
   Welches Problem löst der Prototyp? Woran wird Erfolg gemessen?

2. Zielgruppe / Szenario
   Wer nutzt den Prototyp, in welchem Kontext?

3. Funktionale Anforderungen (aus Gestaltungsprinzipien abgeleitet)
   ID | Anforderung | Zugehöriges Gestaltungsprinzip | Priorität (Muss/Soll/Kann)

4. Nicht-Ziele (explizit außerhalb des Scopes)

5. Erfolgskriterien für die Evaluation
```

### Ausgefülltes Beispiel

```
Projektname: Onboarding-MAS-Prototyp
Datum: [Datum]
Version: 0.1

1. Problem & Ziel
   Neue Mitarbeiter:innen sollen durch ein agentisches KI-System onboarded
   werden, ohne klassisches, sichtbares Interface. Ziel: zeigen, dass
   Transparenz und situative Kontrolle wahrgenommene Sicherheit fördern.

2. Zielgruppe / Szenario
   Testpersonen in der Rolle "neue:r Mitarbeiter:in bei fiktiver Firma X",
   interagieren über peripheren Statuspunkt + Chat mit MAS.

3. Funktionale Anforderungen
   ID  | Anforderung                                          | Prinzip        | Priorität
   F01 | Agent erklärt vor kritischen Aktionen Grund und       | Transparenz    | Muss
       | nächsten Schritt, entsprechend dem konfigurierten                    |
       | Transparenzgrad                                                      |
   F02 | Nutzer:in kann jede kritische Aktion bestätigen,       | Situative      | Muss
       | anpassen oder ablehnen                                | Kontrolle      |
   F03 | Statuspunkt zeigt Systemzustand über Form/Farbe an,   | Calm Tech      | Muss
       | ohne dauerhaftes Fenster                                             |
   F04 | Bei unklarer Anfrage bietet Agent Auswahloptionen an  | Transparenz    | Soll
   F05 | Sprachein­gabe als Alternative zu Tippen (push-to-talk)| Situative      | Kann
       |                                                        | Kontrolle      |
   F06 | Kommunikationsstil passt sich an Vorab-Umfrage an     | Vertrauen      | Kann

4. Nicht-Ziele
   - Keine Anbindung an echte Firmensysteme (Sandbox-Umgebung statt real)
   - Kein echtes System-Level-Screen-Capture
   - Keine produktionsreife Sicherheits-/Skalierungsarchitektur

5. Erfolgskriterien für die Evaluation
   - Testpersonen können nach der Interaktion korrekte Aussagen
     über das Systemverhalten treffen (mentales Modell, RQ1)
   - Testpersonen können benennen, an welchen Stellen sie eingreifen
     konnten und warum das System gehandelt hat (erlebte
     Transparenz und Kontrolle, RQ2/RQ3)
   - Die Interaktionsprotokolle zeigen, ob die gewählte
     Konfiguration dort bestätigt hat, wo es die Kritikalitätsregel
     vorsieht
```

---

## 2. ADR-Template (Architecture Decision Record)

Ein ADR pro wichtiger technischer Entscheidung – kurz halten, ein Dokument reicht meist eine halbe Seite.

### Vorlage

```
ADR-[Nummer]: [Kurztitel der Entscheidung]
Datum:
Status: [vorgeschlagen / entschieden / überholt]

Kontext
  Welches Problem/welche Frage stand zur Entscheidung an?

Betrachtete Optionen
  Option A: ...
  Option B: ...
  (ggf. Option C)

Entscheidung
  Gewählte Option + kurze Begründung

Konsequenzen
  Was folgt daraus (positiv wie negativ)?
```

### Ausgefüllte Beispiele

```
ADR-001: Agentenframework
Status: entschieden

Kontext
  Für die MAS-Orchestrierung wird ein Framework benötigt, das explizite
  Kontrollpunkte (Human-in-the-loop) unterstützt, da dies zentral für
  die Forschungsfrage zu situativer Kontrolle ist.

Betrachtete Optionen
  A: LangGraph – expliziter State-Graph, eingebaute Interrupt-Mechanik
  B: CrewAI – rollenbasiert, schnell für lineare Workflows
  C: AutoGen/AG2 – Weiterentwicklung verlangsamt (Stand 2026)

Entscheidung
  LangGraph, da die interrupt()-Mechanik direkt die geforderte situative
  Kontrolle abbildet und der explizite State jederzeit inspizierbar ist
  (= Transparenz).

Konsequenzen
  + Sehr gute Passung zu den Forschungsfragen
  + Eingebautes Checkpointing für pausierte Abläufe
  - Steilere Lernkurve als CrewAI, mehr Boilerplate-Code
```

```
ADR-002: Screen-Kontext ohne echtes Screen-Capture
Status: entschieden

Kontext
  Der Prototyp soll den Bildschirmkontext der Nutzer:in einbeziehen
  können, ohne dass Testpersonen ihren echten Bildschirm freigeben
  müssen (Datenschutz, Vergleichbarkeit zwischen Testpersonen).

Betrachtete Optionen
  A: Echtes System-Level-Screen-Capture (OS-APIs)
  B: Simulierte Firmenumgebung (Sandbox) innerhalb der eigenen App,
     Agent liest internen App-Zustand statt echtem Screenshot
  C: Wizard-of-Oz – Screen-Ereignisse manuell simuliert

Entscheidung
  Option B. Der Effekt "Agent sieht Kontext" wird durch direkten Zugriff
  auf den App-eigenen State erzeugt, keine echten Nutzerdaten involviert.

Konsequenzen
  + Kein Datenschutzrisiko, keine Einwilligungsproblematik
  + Identische, kontrollierte Inhalte für alle Testpersonen
  + Geringerer Implementierungsaufwand (keine plattformspezifischen
    Capture-APIs nötig)
  - Reduzierte externe Validität: reale Systemintegration wäre für
    ein Produktivsystem nötig (siehe Limitationen, Kapitel 6.1)
```

```
ADR-003: App-Hülle für Statuspunkt
Status: entschieden

Kontext
  Der periphere Statuspunkt soll als eigenständige App auftreten,
  möglichst ressourcenschonend und im Sinne von Calm Technology dezent.

Betrachtete Optionen
  A: Electron – etabliert, bringt eigenes Chromium mit (~100+ MB)
  B: Tauri – nutzt System-Webview, deutlich schlanker (im niedrigen
     MB-Bereich)

Entscheidung
  Tauri, da der Ressourcenverbrauch besser zum Designziel "dezent,
  kaum wahrnehmbar" passt als eine vollständige Browser-Instanz.

Konsequenzen
  + Schlanke, performante App passend zum Calm-Tech-Prinzip
  + React/TypeScript-Frontend wie geplant nutzbar
  - Rust-Grundkenntnisse für die native Hülle nötig (überschaubar,
    da Kernlogik im Python-Backend bleibt)
  - Kleineres Ökosystem/weniger Community-Ressourcen als Electron
```

```
ADR-004: Guardrail-Strategie für den eingebetteten Agenten
Status: entschieden (Ebenen 1-3 im Code umgesetzt, Pilot-Test/Red-Teaming offen)

Kontext
  Der Agent basiert auf einem echten LLM, ist also nicht vollständig
  gescriptet – Testpersonen interagieren frei, nicht nur entlang fixer
  Pfade wie in der quantitativen Vignetten-Studie. Es braucht Leitplanken,
  damit der Agent im Szenario bleibt, keine Aktionen außerhalb der
  Sandbox auslösen kann und mit Grenzfällen (Unsicherheit, bewusste
  Manipulationsversuche) kontrolliert umgeht.

Betrachtete Optionen
  A: Nur Prompt-Disziplin (System-Prompt definiert Grenzen)
  B: Mehrschichtiges System aus Prompt + technischer Tool-Beschränkung +
     Eskalations-Fallback + Pilot-Test/Red-Teaming vor der Studie

Entscheidung
  Option B. Reine Prompt-Disziplin (A) ist umgehbar und daher als
  alleinige Absicherung nicht ausreichend. Die eigentlich robuste Ebene
  ist die technische Tool-Beschränkung: Der Agent bekommt im LangGraph-
  Setup nur Zugriff auf klar definierte Sandbox-Funktionen
  (create_ticket(), add_calendar_event(), send_message() etc.) – selbst
  bei einer aus der Rolle gedrängten Textantwort kann er technisch nichts
  außerhalb der Sandbox auslösen, da es schlicht keine anderen Funktionen
  gibt, die er aufrufen könnte.

  Vier Ebenen im Detail:
  1. System-Prompt: Rolle, erlaubte Themen, Verhalten bei Unsicherheit
     (Standardweg: Eskalation, nicht Raten/Improvisieren)
  2. Technische Tool-Beschränkung (siehe oben) – die eigentlich wirksame
     Ebene, nicht nur Text
  3. Eskalations-Fallback als definierter Zweig im Graphen (dient
     gleichzeitig als Forschungsmoment und als Sicherheitsnetz)
  4. Pilot-Test / gezieltes Red-Teaming vor der eigentlichen Studie
     (bewusst versuchen, den Agenten aus der Rolle zu drängen)

Konsequenzen
  + Robuster als reine Prompt-Disziplin, da Tool-Zugriff strukturell
    begrenzt ist, nicht nur durch Anweisung
  + Eskalations-Fallback ist Doppelnutzen: Forschungsmoment (RQ2/RQ3)
    UND Sicherheitsnetz
  + Stärkt die Validität der Studie: dokumentierte Absicherung, falls
    eine Testperson den Agenten "kaputt macht"
  - Zusätzlicher Implementierungsaufwand (Tool-Whitelisting, Pilot-Test
    als eigener Zeitblock im Zeitplan)
  - Red-Teaming vor der Studie ersetzt keine kontinuierliche Überwachung
    während der eigentlichen Testphase – bei Bedarf in Limitationen
    (Kapitel 6.1) benennen
```

---

### Vorlage

```
ID | Risiko | Wahrscheinlichkeit (niedrig/mittel/hoch) | Auswirkung (niedrig/mittel/hoch) | Gegenmaßnahme
```

### Ausgefülltes Beispiel

```
ID  | Risiko                                    | Wahrsch. | Auswirkung | Gegenmaßnahme
R01 | LLM antwortet unvorhersehbar/inkonsistent | mittel   | hoch       | Kontrolliertes Sandbox-
    | während der Nutzerstudie                  |          |            | Szenario mit gescripteten
    |                                            |          |            | Eingaben, Pilotdurchlauf
    |                                            |          |            | vor eigentlicher Studie
R02 | Zeitplan wird durch technische Probleme    | mittel   | hoch       | MVP-Scope bewusst eng
    | (Woche 10-11) gefährdet                    |          |            | halten; Sprache/Personali-
    |                                            |          |            | sierung als Kann-Features
    |                                            |          |            | zuerst streichbar
R03 | Zu wenige Testpersonen für aussagekräftige | mittel   | mittel     | Frühzeitige Rekrutierung
    | Studie (Woche 12-13)                       |          |            | parallel zur Entwicklung
    |                                            |          |            | starten (siehe LinkedIn-
    |                                            |          |            | Interviewanfragen)
R04 | Testpersonen interpretieren Sandbox als    | niedrig  | mittel     | Klare Vignette/Instruktion
    | "nicht echt" und reagieren unnatürlich     |          |            | zu Beginn der Studie
R05 | Rive-Einarbeitung dauert länger als geplant| niedrig  | niedrig    | CSS-Animation als Fallback
    | (Design-Teil)                              |          |            | bereithalten
R06 | macOS-Berechtigungsprobleme (Sandbox,      | mittel   | mittel     | Tatsächlich eingetreten:
    | TCC-Schutz für Desktop, npm-Cache-Rechte)  |          |            | Projekt in ~/Projects statt
    | verzögern die Entwicklung                  |          |            | ~/Desktop verschoben,
    |                                            |          |            | npm-Cache-Besitzrechte
    |                                            |          |            | korrigiert; bei neuen
    |                                            |          |            | Fehlern gezielt einzeln lösen
R07 | Dokumentation und tatsächlicher Figma-/    | hoch     | mittel     | Tatsächlich eingetreten
    | Code-Stand laufen auseinander (z.B. Namen, |          |            | (mehrfach): regelmäßiger
    | Farbwerte, Statuslogik)                    |          |            | Abgleich Doku↔Figma/Code
    |                                            |          |            | vor größeren Bauschritten,
    |                                            |          |            | Figma/Code als Quelle der
    |                                            |          |            | Wahrheit bei Widerspruch
R08 | Layout-/CSS-Fehler (z.B. Flexbox-Breiten-  | mittel   | niedrig    | Tatsächlich eingetreten,
    | Vererbung) kosten überproportional viel    |          |            | gelöst durch systematisches
    | Debugging-Zeit                             |          |            | Eingrenzen von außen nach
    |                                            |          |            | innen (Elternkette prüfen)
```

---

*Hinweis: Diese Vorlagen sind bewusst schlank gehalten. Für die Bachelorarbeit reicht es, ADRs und Risiko-Register als Anhang oder kurze Erwähnung in Kapitel 3 (Methodik) bzw. 6.1 (Limitationen) einzubinden – sie müssen nicht als eigenständige Kapitel ausformuliert werden.*
