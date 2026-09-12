"""
Leitet den Begründungsblock ("N Schritte") strukturell aus dem Graph-Zustand
ab - Prinzip analog zur Logging-Architektur in Setup_Dokumentation.md
Abschnitt 7 (strukturell markieren statt Text raten/schätzen).

info_agent_node und escalate_node schreiben inzwischen zwei zusätzliche,
rein additive State-Felder (siehe agent/graph.py):
  - state["last_search_results"]: die Rückgabe von search_documents (Liste,
    ggf. leer) - Grundlage für den "Wissensdatenbank durchsucht"-Schritt.
  - state["last_colleague"]: die per find_colleague_for_topic ermittelte
    Person (oder None) - Grundlage für den "An <Person> übergeben"-Schritt.
Beide Felder werden von KEINEM anderen Knoten/Routing gelesen - reine
Informationsquelle für diese Datei.
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
      - search_documents (state["last_search_results"]) -> ein Schritt PRO
        gefundenem Treffer, mit source={"title","path"}; bei einer
        durchgeführten, aber ergebnislosen Suche EIN Schritt ohne source
        statt gar keinem (die Suche hat stattgefunden, auch wenn sie
        nichts fand - das gehört zur Ehrlichkeit der Zahl dazu). Der
        Unterschied "Feld fehlt" (kein Suchlauf, anderer Knoten) vs. "Feld
        ist []" (Suchlauf ohne Treffer) wird über state.get(...) is not None
        geprüft, nicht über einen simplen Wahrheitswert-Check.
      - Eskalation (state["last_colleague"]) -> "An <Person> übergeben",
        NUR wenn tatsächlich jemand gefunden wurde (find_colleague_for_topic
        kann None liefern - dann kein Schritt, statt eine Person zu
        erfinden).
      - create_ticket-Vorschlag (state["pending_action"])
      - add_calendar_event-/send_message-Vorschlag (Mapping vorbereitet,
        aber aktuell UNERREICHBAR: kein Graph-Knoten erzeugt diese
        Tool-Namen bisher - siehe Bericht an die Nutzerin).

    HINWEIS zur Zeitlichkeit: pending_action beschreibt die VORGESCHLAGENE
    Aktion zum Zeitpunkt, an dem der Prüfer die Antwort freigegeben hat -
    NICHT den Zeitpunkt der tatsächlichen Ausführung (die passiert erst
    nach Bestätigung, in einem separaten execute_action_node-Schritt, ggf.
    sogar nach abweichendem Nutzer-Eingriff). Labels sind deshalb bewusst
    im Vorschlags-Modus formuliert ("... vorgeschlagen"/"vorbereitet"),
    NICHT im Ausführungs-Modus ("... erstellt") - siehe Bericht an die
    Nutzerin zum fehlenden Gegenstück nach execute_action_node.
    """
    if not transparency_allows_rationale(state_values.get("transparency_level")):
        return None

    steps: list[dict] = []

    correction_count = state_values.get("correction_count") or 0
    for _ in range(correction_count):
        steps.append(
            {"label": "Antwort überprüft und überarbeitet", "detail": None, "source": None}
        )

    steps.extend(_steps_for_search_results(state_values.get("last_search_results")))
    steps.extend(_steps_for_colleague(state_values.get("last_colleague")))

    pending_action = state_values.get("pending_action")
    if pending_action:
        steps.extend(_steps_for_pending_action(pending_action))

    return {"steps": steps}


def _steps_for_search_results(last_search_results: Optional[list]) -> list[dict]:
    # None = dieser Knotendurchlauf hat gar nicht gesucht (Feld fehlt, siehe
    # Modul-Docstring) - zu unterscheiden von [] (Suche lief, fand nichts).
    if last_search_results is None:
        return []

    if not last_search_results:
        return [
            {
                "label": "Wissensdatenbank durchsucht",
                "detail": "Keine passenden Inhalte gefunden.",
                "source": None,
            }
        ]

    steps = []
    for result in last_search_results:
        title = result.get("title")
        steps.append(
            {
                "label": "Wissensdatenbank durchsucht",
                "detail": result.get("summary"),
                # "path" existiert nur bei KNOWLEDGE_ARTICLES, nicht bei
                # INTRANET_POSTS (siehe knowledge_data.py) - .get() statt [...],
                # damit ein Intranet-Treffer keinen KeyError auslöst.
                "source": {"title": title, "path": result.get("path")} if title else None,
            }
        )
    return steps


def _steps_for_colleague(last_colleague: Optional[dict]) -> list[dict]:
    if not last_colleague:
        return []
    name = last_colleague.get("name")
    if not name:
        return []
    department = last_colleague.get("department")
    return [
        {
            "label": f"An {name} übergeben",
            "detail": f"{department} - {last_colleague.get('role')}" if department else last_colleague.get("role"),
            "source": None,
        }
    ]


def build_execution_rationale(state_values: dict[str, Any]) -> Optional[dict]:
    """Rationale für die Bestätigungsnachricht aus execute_action_node -
    Gegenstück zu build_rationale() im AUSFÜHRUNGS-Modus ("... erstellt"/
    "eingetragen"/"gesendet" statt "vorgeschlagen"/"vorbereitet").

    Braucht state["last_executed_action"] statt state["pending_action"] -
    Letzteres ist zu diesem Zeitpunkt (nach execute_action_node) bereits
    auf None zurückgesetzt (siehe agent/graph.py).

    Bewusst EIGENE Funktion statt Wiederverwendung von build_rationale():
    die Bestätigungsnachricht soll nur den Ausführungs-Schritt zeigen, nicht
    zusätzlich die Korrekturschleife/Suchtreffer/Kolleg:in-Schritte der
    VORHERIGEN (Vorschlags-)Nachricht wiederholen, die state_values an
    dieser Stelle ebenfalls noch trüge.
    """
    if not transparency_allows_rationale(state_values.get("transparency_level")):
        return None

    action = state_values.get("last_executed_action")
    if not action:
        return {"steps": []}

    return {"steps": _steps_for_executed_action(action)}


def _steps_for_executed_action(action: dict) -> list[dict]:
    tool = action.get("tool")
    reason = action.get("reason")

    if tool == "create_ticket":
        department = action.get("department")
        label = f"Ticket bei {department} erstellt" if department else "Ticket erstellt"
        return [{"label": label, "detail": reason, "source": None}]

    if tool == "add_calendar_event":
        return [{"label": "Termin eingetragen", "detail": reason, "source": None}]

    if tool == "send_message":
        to = (action.get("args") or {}).get("to")
        label = f"Nachricht an {to} gesendet" if to else "Nachricht gesendet"
        return [{"label": label, "detail": reason, "source": None}]

    return []


def _steps_for_pending_action(pending_action: dict) -> list[dict]:
    """Labels bewusst im VORSCHLAGS-Modus, nicht im Ausführungs-Modus - siehe
    Docstring von build_rationale(). Die Ausführung selbst passiert erst
    nach Bestätigung in execute_action_node, für die es aktuell KEINE
    eigene Assistenz-Nachricht gibt, an die ein "... erstellt"-Schritt
    angehängt werden könnte (siehe Bericht an die Nutzerin)."""
    tool = pending_action.get("tool")
    reason = pending_action.get("reason")

    if tool == "create_ticket":
        department = pending_action.get("department")
        label = f"Ticket bei {department} vorgeschlagen" if department else "Ticket vorgeschlagen"
        return [{"label": label, "detail": reason, "source": None}]

    if tool == "add_calendar_event":
        # Aktuell unerreichbar - kein scheduling_agent vorhanden, siehe
        # Setup_Dokumentation.md Abschnitt 8 ("noch offen").
        return [{"label": "Termin vorgeschlagen", "detail": reason, "source": None}]

    if tool == "send_message":
        # Aktuell unerreichbar - kein Knoten erzeugt diesen pending_action-Typ.
        to = (pending_action.get("args") or {}).get("to")
        label = f"Nachricht an {to} vorbereitet" if to else "Nachricht vorbereitet"
        return [{"label": label, "detail": reason, "source": None}]

    return []
