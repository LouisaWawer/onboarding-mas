"""
State-Schema für den Onboarding-Agenten (erweitert um Supervisor/Prüfer-Kreislauf).
"""

from typing import TypedDict, Literal, Optional


TransparencyLevel = Literal["high", "medium", "low"]
ControlLevel = Literal["high", "medium", "low"]
CheckTarget = Literal["initial_request", "next_subtask", "subagent_query", "correction"]
PrueferVerdict = Literal["freigabe", "beanstandung"]


class PendingAction(TypedDict):
    tool: str
    args: dict
    reason: str
    department: Optional[str]
    is_critical: bool  # steuert L2 (Warnmeldung statt Konfidenzwert) und G3 (interrupt-Pflicht)


class OnboardingState(TypedDict):
    messages: list
    session_id: str

    current_task: Optional[str]
    active_agent: str  # "infrastructure_agent" | "escalate" | ...

    transparency_level: TransparencyLevel
    control_level: ControlLevel

    # Supervisor/Prüfer-Kreislauf
    check_target: CheckTarget
    subtasks: list[dict]          # [{"subtask": str, "category": str}, ...] - Zerlegung der Nachricht
    subtask_index: int            # welcher Teilschritt aktuell bearbeitet wird
    pruefer_verdict: Optional[PrueferVerdict]
    pruefer_issues: list[str]
    correction_count: int  # Abbruchbedingung: nach Überschreiten -> escalate

    # G13: Kontext-Check vor Ausführung
    pending_action: Optional[PendingAction]
    pending_action_snapshot: Optional[dict]
    context_changed: bool
    change_description: Optional[str]

    # Entwurf einer Sub-Agenten-Antwort, VOR Prüfer-Freigabe - wird erst bei
    # "freigabe" permanent an messages angehängt. Verhindert, dass abgelehnte
    # Entwürfe (Korrekturschleife) sichtbar in der Historie landen UND
    # verhindert das API-Problem "zwei Assistant-Nachrichten hintereinander".
    draft_response: Optional[str]

    dot_status: Literal["idle", "active", "waiting"]
    sandbox_state: dict
    channel: Literal["dm", "status_panel"]

    # Rein informativ für den Begründungsblock ("rationale") der API-Schicht
    # (backend/api/rationale.py) - von KEINEM Knoten/Routing hier im Graphen
    # gelesen, nur geschrieben.
    last_search_results: Optional[list[dict]]  # info_agent_node: Rückgabe von search_documents
    last_colleague: Optional[dict]             # escalate_node: Rückgabe von find_colleague_for_topic
    last_executed_action: Optional[PendingAction]  # execute_action_node: die gerade ausgeführte Aktion (pending_action ist zu diesem Zeitpunkt schon auf None gesetzt)

    # human_review_node/updated_query_node: die vom interrupt() zurückgegebene
    # Entscheidung ("bestätigen"/"anpassen"/"ablehnen"/"trotzdem bestätigen"/
    # "abbrechen") und der dabei abgelehnte/anzupassende Vorschlag (pending_action
    # ist zu diesem Zeitpunkt schon auf None gesetzt) - execute_action_node
    # braucht beides, um bei Ablehnung/Anpassung reagieren zu können, ohne das
    # mit "kein Vorschlag existierte" (z.B. info_agent-Pfad) zu verwechseln.
    last_decision: Optional[str]
    last_declined_action: Optional[PendingAction]

    # Duplikat-Erkennung über Anfragen-Grenzen hinweg (siehe Bericht an die
    # Nutzerin, Punkt 5): sandbox_state ist PRO THREAD, eine neue Anfrage
    # sieht Tickets aus anderen Anfragen derselben Sitzung sonst nie.
    # session_open_tickets wird VON DER API-SCHICHT (routes.py, vor jedem
    # neuen Turn) session-weit befüllt (nur offene Tickets) - read-only für
    # den Graphen, kein Knoten hier schreibt es. duplicate_notice wird von
    # infrastructure_agent_node gesetzt, wenn ein neuer Ticket-Vorschlag
    # inhaltlich mit einem bestehenden offenen Ticket übereinstimmt, und von
    # human_review_node als change_notice der Bestätigungskarte genutzt
    # (dieselbe Warnkarten-Optik wie der G13-Fall).
    session_open_tickets: list[dict]
    duplicate_notice: Optional[str]
