"""
Leitet den Begründungsblock ("N Schritte") strukturell aus dem Graph-Zustand
ab - Prinzip analog zur Logging-Architektur in Setup_Dokumentation.md
Abschnitt 7 (strukturell markieren statt Text raten/schätzen).

WICHTIG, siehe Bericht an die Nutzerin: DREI der im Auftrag genannten
Schritttypen werden hier bewusst NICHT erzeugt, weil graph.py die dafür
nötigen Informationen aktuell nicht in den State schreibt (nur als lokale
Variable in der jeweiligen Node-Funktion verwendet, nie zurückgegeben):

  - search_documents  -> Artikel-Titel/-Pfad (info_agent_node: `results`)
  - reference_colleague / escalate_node -> Kolleg:in-Name (escalate_node:
    `colleague`)

Der Auftrag verlangt ausdrücklich: "Falls du eine Ableitung nicht sauber
aus dem State hinbekommst: den Schritt weglassen ... Nichts schätzen,
keine Platzhalterschritte." Diese beiden Fälle fehlen deshalb hier -
nicht aus Versehen.
"""

from __future__ import annotations

from typing import Any, Optional

# Gleiche Regel wie die "explain"-Kategorie im Logging-Beispiel aus
# Setup_Dokumentation.md Abschnitt 7 / prompts_config.py-Analogie:
# explains = transparency_level in ("high", "medium").
RATIONALE_TRANSPARENCY_LEVELS = ("high", "medium")


def transparency_allows_rationale(transparency_level: Optional[str]) -> bool:
    return transparency_level in RATIONALE_TRANSPARENCY_LEVELS


def build_rationale(state_values: dict[str, Any]) -> Optional[dict]:
    """Baut {"steps": [...]} rein aus state_values (dem, was graph.py
    tatsächlich in den State schreibt). Gibt None zurück, wenn der
    konfigurierte transparency_level rationale gar nicht vorsieht.

    Aktuell abgedeckt:
      - Korrekturschleife (state["correction_count"]) -> ein Schritt pro
        Korrekturversuch für DIESEN Teilschritt (correction_count wird bei
        jedem neuen Teilschritt auf 0 zurückgesetzt, siehe supervisor_node
        check_target == "next_subtask" - die Zahl ist also bereits korrekt
        auf die aktuelle Nachricht begrenzt, nicht kumulativ über die ganze
        Anfrage).
      - create_ticket-Vorschlag (state["pending_action"])
      - add_calendar_event-/send_message-Vorschlag (Mapping vorbereitet,
        aber aktuell UNERREICHBAR: kein Graph-Knoten erzeugt diese
        Tool-Namen bisher - siehe Bericht an die Nutzerin).

    HINWEIS zur Zeitlichkeit: pending_action beschreibt die VORGESCHLAGENE
    Aktion zum Zeitpunkt, an dem der Prüfer die Antwort freigegeben hat -
    NICHT den Zeitpunkt der tatsächlichen Ausführung (die passiert erst
    nach Bestätigung, in einem separaten execute_action_node-Schritt,
    ggf. sogar nach abweichendem Nutzer-Eingriff). Das Label "... erstellt"
    ist wörtlich aus dem Auftrag übernommen; siehe Bericht an die Nutzerin,
    ob das absichtlich so gemeint ist oder "vorgeschlagen" treffender wäre.
    """
    if not transparency_allows_rationale(state_values.get("transparency_level")):
        return None

    steps: list[dict] = []

    correction_count = state_values.get("correction_count") or 0
    for _ in range(correction_count):
        steps.append(
            {"label": "Antwort überprüft und überarbeitet", "detail": None, "source": None}
        )

    pending_action = state_values.get("pending_action")
    if pending_action:
        steps.extend(_steps_for_pending_action(pending_action))

    return {"steps": steps}


def _steps_for_pending_action(pending_action: dict) -> list[dict]:
    tool = pending_action.get("tool")
    reason = pending_action.get("reason")

    if tool == "create_ticket":
        department = pending_action.get("department")
        label = f"Ticket bei {department} erstellt" if department else "Ticket erstellt"
        return [{"label": label, "detail": reason, "source": None}]

    if tool == "add_calendar_event":
        # Aktuell unerreichbar - kein scheduling_agent vorhanden, siehe
        # Setup_Dokumentation.md Abschnitt 8 ("noch offen").
        return [{"label": "Termin eingetragen", "detail": reason, "source": None}]

    if tool == "send_message":
        # Aktuell unerreichbar - kein Knoten erzeugt diesen pending_action-Typ.
        to = (pending_action.get("args") or {}).get("to")
        label = f"Nachricht an {to} vorbereitet" if to else "Nachricht vorbereitet"
        return [{"label": label, "detail": reason, "source": None}]

    return []
