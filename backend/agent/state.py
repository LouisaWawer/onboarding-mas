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
