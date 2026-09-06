"""
Tools, auf die der Agent Zugriff hat.

Wichtig (ADR-004, Leitplanken): Der Agent kann NUR diese Funktionen aufrufen.
Das ist die eigentlich wirksame Absicherung - nicht der System-Prompt allein.
Jede Funktion schreibt ausschließlich in sandbox_state, nie auf echte Systeme.
"""

from datetime import datetime

from .knowledge_data import search_knowledge_and_intranet
from .colleague_data import find_colleague_for_topic


def create_ticket(sandbox_state: dict, department: str, subject: str) -> dict:
    """Legt ein neues Ticket in der Sandbox an (kein echtes Ticketsystem)."""
    ticket = {
        "id": f"N{len(sandbox_state.get('tickets', [])) + 1:04d}",
        "date": datetime.now().strftime("%d.%m."),
        "subject": subject,
        "department": department,
        "status": "offen",
        "is_new": True,
    }
    sandbox_state.setdefault("tickets", []).append(ticket)
    return ticket


def add_calendar_event(sandbox_state: dict, date: str, time: str, title: str, organizer: str) -> dict:
    """Trägt einen Termin in den Sandbox-Kalender ein."""
    event = {"date": date, "time": time, "title": title, "organizer": organizer}
    sandbox_state.setdefault("calendar_events", []).append(event)
    return event


def send_message(sandbox_state: dict, to: str, text: str) -> dict:
    """Sendet eine Nachricht in einen bestehenden Chat-Thread der Sandbox."""
    message = {"from": "Lumi", "to": to, "text": text, "timestamp": datetime.now().isoformat()}
    sandbox_state.setdefault("messages", []).append(message)
    return message


def search_documents(sandbox_state: dict, query: str) -> list[dict]:
    """Durchsucht Knowledge Hub + Intranet nach passenden Inhalten (siehe knowledge_data.py).

    Gibt eine Liste vorschlagbarer Dokumente zurück (Titel, Pfad/Kategorie,
    Zusammenfassung, Quelle) - der Agent formuliert daraus seinen Vorschlag,
    erfindet aber keine Inhalte, die es nicht gibt.
    """
    return search_knowledge_and_intranet(query)


def create_onboarding_plan(sandbox_state: dict) -> list[dict]:
    """Erstellt/liefert den Onboarding-Plan (lebt beim Agenten/Chat, nicht im Intranet -
    siehe Diskussion zur Unpersonalisiertheit des Intranets).

    Wird beim ersten Aufruf initialisiert, danach nur der bestehende Stand
    zurückgegeben (Fortschritt bleibt über die Sitzung erhalten).
    """
    if "onboarding_plan" not in sandbox_state:
        sandbox_state["onboarding_plan"] = [
            {"task": "Willkommensnachricht gelesen", "done": False},
            {"task": "VPN-Zugang eingerichtet", "done": False},
            {"task": "Team-Meeting im Kalender eingetragen", "done": False},
            {"task": "Knowledge Hub erkundet", "done": False},
        ]
    return sandbox_state["onboarding_plan"]


def update_onboarding_plan(sandbox_state: dict, task: str, done: bool = True) -> list[dict]:
    """Markiert einen Onboarding-Schritt als erledigt (oder zurückgesetzt)."""
    plan = sandbox_state.get("onboarding_plan", [])
    for item in plan:
        if item["task"] == task:
            item["done"] = done
    return plan


def reference_colleague(sandbox_state: dict, topic: str) -> dict | None:
    """Findet die zuständige Person zu einem Thema (siehe colleague_data.py).

    Nutzt echte, vordefinierte Personendaten - der Agent erfindet keine
    Namen/Zuständigkeiten (Leitplanke gegen Halluzination bei Verweisen).
    """
    return find_colleague_for_topic(topic)


# Registry, die im Graphen genutzt wird - bewusst als geschlossene Liste,
# nicht dynamisch erweiterbar, damit die Tool-Beschränkung aus ADR-004 greift.
AVAILABLE_TOOLS = {
    "create_ticket": create_ticket,
    "add_calendar_event": add_calendar_event,
    "send_message": send_message,
    "search_documents": search_documents,
    "create_onboarding_plan": create_onboarding_plan,
    "update_onboarding_plan": update_onboarding_plan,
    "reference_colleague": reference_colleague,
}
