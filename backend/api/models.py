"""
Pydantic-Schemas für die FastAPI-Schicht (backend/api/). Reine
Request-/Response-Formen - keine Graph-Logik hier, siehe agent/graph.py.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

# "result"/"error": peripheres Signal nach Laufende bzw. Fehlerfall,
# Guideline 10/Calm-Technology-Kern der Arbeit. "suggestion": proaktiver
# Vorschlag beim Screenwechsel (Guideline 21) - SESSION-, nicht
# Thread-gebunden (siehe SessionSnapshotResponse.pending_suggestion und
# Bericht an die Nutzerin), taucht deshalb in status_changed-Events mit
# thread_id=null auf, nie in AnfrageSummary.status.
StatusValue = Literal["idle", "working", "waiting", "result", "error", "suggestion"]


class CreateSessionRequest(BaseModel):
    access_code: str


class AnfrageSummary(BaseModel):
    thread_id: str
    title: Optional[str] = None
    created_at: str
    last_active_at: str
    # Pro Anfrage, nicht pro Session: mehrere Anfragen derselben Session
    # können gleichzeitig "result" o.ä. tragen (siehe Bericht an die
    # Nutzerin) - welcher Zustand am peripheren Punkt gewinnt, wenn mehrere
    # Anfragen etwas zu zeigen haben, ist eine Frontend-/Calm-Technology-
    # Entscheidung, keine Backend-Entscheidung.
    status: StatusValue


class SuggestionOption(BaseModel):
    """Eine Options-Zeile der Vorschlagskarte (siehe suggestion_policy.py).
    `displayed` ist das kurze Options-Label (Button-Text), `submitted` der
    tatsächliche Nutzernachrichten-Text nach einem Klick - beide verlassen
    das Backend jetzt einzeln (Korrektur ggü. der früheren Einzelzeilen-
    Fassung, siehe suggestion_policy.py-Docstring: `submitted` wurde dort
    nie übertragen)."""

    displayed: str
    submitted: str


class PendingSuggestion(BaseModel):
    """Session-gebundener Vorschlag (siehe Bericht an die Nutzerin, Schritt
    6) - eine Karte (Titel + mehrere Optionen), keine Einzelzeile mehr.

    `acknowledged` (Testpunkt-8-Nachbesserung): True, wenn das Panel bereits
    geöffnet wurde (Punkt beruhigt), OHNE dass der Vorschlag selbst schon
    verworfen wurde (Klick/X/Screenwechsel) - siehe
    resolve_pending_suggestion()/acknowledge_pending_suggestion()
    (store.py)."""

    screen: str
    title: str
    options: list[SuggestionOption]
    acknowledged: bool = False


class SessionSnapshotResponse(BaseModel):
    """Antwort von POST /session und GET /session/{session_id} - dieselbe
    Form für beide, siehe Auftrag Punkt 2 ("eine Datenquelle, drei
    Ansichten")."""

    session_id: str
    anfragen: list[AnfrageSummary]
    active_thread_id: Optional[str] = None
    pending_suggestion: Optional[PendingSuggestion] = None


class AnfrageOut(BaseModel):
    thread_id: str
    title: Optional[str] = None
    created_at: str
    last_active_at: str


class RationaleStep(BaseModel):
    label: str
    detail: Optional[str] = None
    source: Optional[dict] = None


class Rationale(BaseModel):
    steps: list[RationaleStep]


class MessageOut(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    rationale: Optional[Rationale] = None


class InterruptOut(BaseModel):
    proposal: Optional[dict] = None
    options: list[str] = []
    change_notice: Optional[str] = None


class ThreadSnapshotResponse(BaseModel):
    thread_id: str
    session_id: str
    status: StatusValue
    messages: list[MessageOut]
    interrupt: Optional[InterruptOut] = None


class PostMessageRequest(BaseModel):
    session_id: str
    text: str = Field(min_length=1)
    channel: Literal["dm", "status_panel"] = "dm"
    # Gesetzt vom Frontend, wenn diese Nachricht aus einem angeklickten
    # Vorschlag stammt (siehe Bericht an die Nutzerin) - explizites Signal
    # statt fragilem Text-Abgleich gegen suggestion_policy.py, damit
    # "suggestion_accepted" zuverlässig geloggt wird, auch wenn ein
    # zukünftiger Wortlaut-Wechsel den abgeschickten Text ändert.
    suggestion_screen: Optional[str] = None


class ResumeRequest(BaseModel):
    session_id: str
    decision: str = Field(min_length=1)


class SeenRequest(BaseModel):
    session_id: str


class ScreenRequest(BaseModel):
    # Geschlossene Liste statt freiem str: eine ECHT unbekannte Screen-ID
    # (Tippfehler/Frontend-Bug) soll als 422 sichtbar werden, nicht
    # stillschweigend verschluckt. 'chat' ist gültig, aber absichtlich
    # nicht in SUGGESTION_POLICY (siehe suggestion_policy.py) - dafür
    # sorgt der Handler, nicht dieser Typ.
    screen: Literal["intranet", "chat", "hub", "tickets", "calendar"]


class AcceptedResponse(BaseModel):
    accepted: bool = True


class TicketOut(BaseModel):
    """Ein von Lumi tatsächlich angelegtes Ticket (sandbox_state["tickets"],
    siehe tools.py: create_ticket()) - Feldnamen an die Frontend-Anzeige
    (Tickets.tsx) angeglichen, nicht 1:1 am Backend-Dict. estimate fehlt
    bewusst: dafür gibt es serverseitig keinen echten Wert (siehe Bericht
    an die Nutzerin) - das Frontend zeigt an dieser Stelle einen expliziten
    Platzhalter statt einer erfundenen Zahl."""

    ticketid: str
    date: str
    topic: str
    department: str
    status: Literal["open", "processing", "done", "error"]
    is_new: bool = True


class TicketsResponse(BaseModel):
    tickets: list[TicketOut]
