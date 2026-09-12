"""
Graph-Struktur: Supervisor + Prüfer um drei Sub-Agenten herum
(infrastructure_agent, info_agent, scheduling_agent) - derselbe
Prüfer-/Kontext-Check-/Bestätigungs-Kreislauf für alle drei, siehe
Architektur-Gespräch: erst den Kreislauf an EINEM Beispiel validiert
(infrastructure_agent), dann auf info_agent und scheduling_agent
übertragen, statt alle gleichzeitig neu zu entwerfen.

Ablauf:
  supervisor --[ok]--> {infrastructure_agent|info_agent|scheduling_agent} --> pruefer
                                                    |
                          [beanstandung, correction_count <= MAX] -> zurück zu supervisor
                          [beanstandung, correction_count > MAX]  -> escalate
                          [freigabe] -> context_check -> announce_confirmation
                                                              |
                          [unverändert] -> human_review -> context_recheck (G13, 2. Vergleich,
                          [geändert]    -> updated_query -+  NACH der 1. Bestätigung)
                                                           |
                                     context_recheck: [unverändert] -> execute_action
                                                       [geändert]    -> updated_query
                                     updated_query -> execute_action | END
"""

from langgraph.graph import StateGraph, END
from langgraph.types import interrupt, Command
from anthropic import Anthropic
from dotenv import load_dotenv
import os

load_dotenv()  # liest backend/.env ein - ohne diesen Aufruf bleibt
                # ANTHROPIC_API_KEY trotz korrekt gefüllter .env-Datei leer

from .state import OnboardingState
from .tools import AVAILABLE_TOOLS
from .colleague_data import find_colleague_for_topic
from .criticality_policy import is_tool_critical
from .prompts_config import build_system_prompt, ESCALATION_PROMPT
from .logging_store import log_interaction

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MAX_CORRECTION_ATTEMPTS = 2

# Bewusst schlanke, leicht erweiter-/kürzbare Liste - Guidelines sind noch
# nicht final. Nicht sinnvoll prüfbare Punkte fliegen raus statt erzwungen
# zu werden (siehe Architektur-Gespräch, Punkt 3).
GENERIC_PHRASES = ["aus verschiedenen gründen", "wie du sicher weißt", "generell gilt"]

# ---------------------------------------------------------------------------
# Tool-Schemas für STRUKTURIERTE Ausgaben (Anthropic Tool Use) - zu
# unterscheiden von AVAILABLE_TOOLS in tools.py, die echte Sandbox-Aktionen
# sind. Diese hier zwingen das Modell zu einem festen Antwortformat, statt
# Text zu parsen (ersetzt die frühere json.loads()-Lösung).
# ---------------------------------------------------------------------------

DECOMPOSE_TOOL = {
    "name": "decompose_request",
    "description": (
        "Zerlegt die Nutzer-Nachricht in einen oder mehrere Teilschritte, "
        "jeweils GENAU EINER Kategorie zugeordnet."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "subtasks": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "subtask": {
                            "type": "string",
                            "description": "Kurze Beschreibung des Teilschritts, 3-8 Wörter",
                        },
                        "category": {
                            "type": "string",
                            "enum": ["infrastructure", "info", "scheduling", "other"],
                            "description": (
                                "'infrastructure' = VPN/Zugänge/Hardware/Software, "
                                "'info' = allgemeine organisatorische Fragen (Urlaub, "
                                "Richtlinien, Onboarding-Themen), "
                                "'scheduling' = Kalendertermine/Besprechungen eintragen, "
                                "'other' = alles andere, auch wenn unklar"
                            ),
                        },
                    },
                    "required": ["subtask", "category"],
                },
            }
        },
        "required": ["subtasks"],
    },
}

PROPOSE_TICKET_TOOL = {
    "name": "propose_ticket",
    "description": "Entscheidet, ob für die aktuelle Anfrage ein IT-Ticket vorgeschlagen werden soll.",
    "input_schema": {
        "type": "object",
        "properties": {
            "needed": {
                "type": "boolean",
                "description": "Ob überhaupt ein Ticket für diese Anfrage nötig ist",
            },
            "subject": {"type": "string", "description": "Kurzer Betreff für das Ticket"},
            "reason": {
                "type": "string",
                "description": "Kurze, der Nutzer:in gezeigte Begründung, warum das Ticket nötig ist",
            },
        },
        "required": ["needed"],
    },
}


PROPOSE_CALENDAR_EVENT_TOOL = {
    "name": "propose_calendar_event",
    "description": "Entscheidet, ob für die aktuelle Anfrage ein Kalendertermin vorgeschlagen werden soll.",
    "input_schema": {
        "type": "object",
        "properties": {
            "needed": {
                "type": "boolean",
                "description": "Ob überhaupt ein Termin für diese Anfrage nötig ist",
            },
            "date": {"type": "string", "description": "Datum des Termins, wie von der Nutzer:in genannt"},
            "time": {"type": "string", "description": "Uhrzeit des Termins, wie von der Nutzer:in genannt"},
            "title": {"type": "string", "description": "Kurzer Titel des Termins"},
            "organizer": {
                "type": "string",
                "description": "Organisator:in des Termins - 'Lumi', falls nicht anders genannt",
            },
            "reason": {
                "type": "string",
                "description": "Kurze, der Nutzer:in gezeigte Begründung, warum der Termin nötig ist",
            },
        },
        "required": ["needed"],
    },
}


def _extract_tool_input(response, tool_name: str) -> dict:
    """Holt den Tool-Use-Block aus einer erzwungenen Tool-Choice-Antwort.
    Bei tool_choice={'type':'tool', 'name': ...} enthält die Antwort GARANTIERT
    genau diesen Block - kein Text-Parsing, kein json.loads() nötig."""
    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return block.input
    raise ValueError(f"Kein Tool-Use-Block für '{tool_name}' in der Antwort gefunden")


def _messages_ending_with_user(messages: list, fallback_instruction: str) -> list:
    """Stellt sicher, dass eine Nachrichtenliste mit einer User-Nachricht endet -
    Anthropic-API-Anforderung ('conversation must end with a user message').

    Wird gebraucht, sobald mehrere Agenten NACHEINANDER auf denselben
    state["messages"]-Verlauf zugreifen (Mehrfach-Teilschritt-Zerlegung):
    Der zweite Sub-Agent würde sonst eine Konversation vorfinden, die mit
    der Antwort des ERSTEN Sub-Agenten (role="assistant") endet. Gibt eine
    NEUE Liste zurück, verändert die übergebene Liste nicht."""
    if messages and messages[-1]["role"] == "assistant":
        return messages + [{"role": "user", "content": fallback_instruction}]
    return messages


# ---------------------------------------------------------------------------
# Supervisor: wiederverwendeter Knoten für Ersteingang UND Korrekturschleife
# ---------------------------------------------------------------------------

import json


def _route_for_category(category: str) -> str:
    """Zentrale Zuordnung Kategorie -> Graph-Knoten."""
    ROUTING_MAP = {
        "infrastructure": "infrastructure_agent",
        "info": "info_agent",
        "scheduling": "scheduling_agent",
    }
    return ROUTING_MAP.get(category, "escalate")


def supervisor_node(state: OnboardingState) -> OnboardingState:
    check_target = state.get("check_target", "initial_request")

    if check_target == "correction":
        state["correction_count"] = state.get("correction_count", 0) + 1
        log_interaction(
            category="correction_loop",
            node="supervisor",
            session_id=state["session_id"],
            task=state.get("current_task"),
            channel=state["channel"],
            attempt=state["correction_count"],
        )
        if state["correction_count"] > MAX_CORRECTION_ATTEMPTS:
            state["active_agent"] = "escalate"
            return state
        # Zurück zur Korrektur DESSELBEN Teilschritts - nicht hart kodiert,
        # sondern der Agent, der für die aktuelle subtask-Kategorie zuständig ist
        current = state["subtasks"][state["subtask_index"]]
        state["dot_status"] = "active"
        state["active_agent"] = _route_for_category(current["category"])
        return state

    if check_target == "next_subtask":
        state["correction_count"] = 0  # pro Teilschritt zurücksetzen
        # pending_action_snapshot ebenfalls pro Teilschritt zurücksetzen - sonst
        # vergleicht context_recheck_node für DIESEN Teilschritt gegen den
        # Snapshot eines VORHERIGEN Teilschritts (der z.B. schon ein Ticket
        # angelegt und damit tickets_count erhöht hat) und meldet fälschlich
        # "geändert", obwohl sich am Kontext DIESER Aktion nichts geändert hat.
        state["pending_action_snapshot"] = None
        state["subtask_index"] += 1
        if state["subtask_index"] >= len(state["subtasks"]):
            state["active_agent"] = "__end__"
            state["dot_status"] = "idle"
            return state
        current = state["subtasks"][state["subtask_index"]]
        state["current_task"] = current["subtask"]
        state["dot_status"] = "active"
        state["active_agent"] = _route_for_category(current["category"])
        return state

    # Ersteingang: Nachricht in einen oder mehrere Teilschritte zerlegen.
    # Tool Use mit erzwungenem tool_choice statt freiem Text + json.loads() -
    # garantiert gültige Struktur, kein Parsing-Fehler möglich.
    state["dot_status"] = "active"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=state["messages"],
        tools=[DECOMPOSE_TOOL],
        tool_choice={"type": "tool", "name": "decompose_request"},
    )
    result = _extract_tool_input(response, "decompose_request")
    subtasks = result["subtasks"]

    state["subtasks"] = subtasks
    state["subtask_index"] = 0
    state["current_task"] = subtasks[0]["subtask"]
    state["active_agent"] = _route_for_category(subtasks[0]["category"])

    log_interaction(
        category="decomposition",
        node="supervisor",
        session_id=state["session_id"],
        channel=state["channel"],
        subtask_count=len(subtasks),
        subtasks=subtasks,
    )
    return state


def route_from_supervisor(state: OnboardingState) -> str:
    return state["active_agent"]


# ---------------------------------------------------------------------------
# Infrastructure-Agent (vormals it_agent)
# ---------------------------------------------------------------------------

def infrastructure_agent_node(state: OnboardingState) -> OnboardingState:
    system_prompt = build_system_prompt(state["transparency_level"])

    # Fokus-Anweisung: die Nutzer-Nachricht kann mehrere Anliegen enthalten,
    # dieser Knoten soll sich NUR um den aktuellen Teilschritt kümmern, nicht
    # die ganze Original-Nachricht erneut aufrollen.
    system_prompt += (
        f"\n\nWICHTIG: Kümmere dich in dieser Antwort AUSSCHLIESSLICH um "
        f"folgenden Teilschritt: \"{state['current_task']}\". Falls die "
        f"ursprüngliche Nachricht weitere Anliegen enthält, werden diese "
        f"separat behandelt - gehe NICHT darauf ein, auch nicht kurz erwähnend."
    )

    if state.get("pruefer_issues"):
        system_prompt += (
            "\n\nDeine letzte Antwort wurde beanstandet: "
            + "; ".join(state["pruefer_issues"])
            + ". Bitte korrigiere das in deiner nächsten Antwort."
        )

    # 1. Antwort-Entwurf generieren. Nachrichtenliste absichern (siehe
    # _messages_ending_with_user) - bei einem zweiten/weiteren Teilschritt
    # ODER einem zweiten Korrekturversuch endet state["messages"] sonst mit
    # einer Assistant-Nachricht, was die API ablehnt.
    call_messages = _messages_ending_with_user(
        state["messages"],
        f"Bitte kümmere dich jetzt um diesen Teilschritt: {state['current_task']}",
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=system_prompt,
        messages=call_messages,
    )
    # WICHTIG: NICHT direkt an state["messages"] anhängen - erst nach
    # Prüfer-Freigabe (siehe pruefer_node). So bleiben abgelehnte Entwürfe
    # aus der Korrekturschleife unsichtbar für die Nutzer:in (wie geplant:
    # "Korrektur läuft nur intern"), UND es entstehen nie zwei
    # Assistant-Nachrichten hintereinander in der gespeicherten Historie.
    state["draft_response"] = response.content[0].text

    # 2. Strukturierte Aktions-Extraktion per Tool Use - basiert auf dem
    # ENTWURF (noch nicht bestätigt), nicht auf state["messages"]. Eigene,
    # rein lokale Nachrichtenliste - landet nirgends in der gespeicherten
    # Historie.
    extraction_messages = call_messages + [
        {"role": "assistant", "content": state["draft_response"]},
        {"role": "user", "content": "Bewerte anhand des bisherigen Gesprächs: ist ein Ticket nötig?"},
    ]
    extraction_response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        system=(
            "Entscheide anhand der Konversation, ob ein IT-Ticket für die "
            "aktuelle Anfrage vorgeschlagen werden soll."
        ),
        messages=extraction_messages,
        tools=[PROPOSE_TICKET_TOOL],
        tool_choice={"type": "tool", "name": "propose_ticket"},
    )
    action_data = _extract_tool_input(extraction_response, "propose_ticket")

    if action_data.get("needed"):
        state["pending_action"] = {
            "tool": "create_ticket",
            "args": {"department": "IT", "subject": action_data.get("subject", "IT-Anliegen")},
            "reason": action_data.get("reason", ""),
            "department": "IT",
            # Feste Policy statt Modelleinschätzung, siehe criticality_policy.py.
            "is_critical": is_tool_critical("create_ticket"),
        }
    else:
        state["pending_action"] = None

    return state


# ---------------------------------------------------------------------------
# Info-Agent: allgemeine organisatorische Fragen, nutzt search_documents
# ---------------------------------------------------------------------------

def info_agent_node(state: OnboardingState) -> OnboardingState:
    query = state["current_task"]
    results = AVAILABLE_TOOLS["search_documents"](state["sandbox_state"], query)
    # Additiv fürs Rationale-Feld der API-Schicht (siehe backend/api/rationale.py) -
    # rein informativ, wird von keinem anderen Knoten/Routing gelesen.
    state["last_search_results"] = results

    system_prompt = build_system_prompt(state["transparency_level"])
    system_prompt += (
        f"\n\nWICHTIG: Kümmere dich in dieser Antwort AUSSCHLIESSLICH um "
        f"folgenden Teilschritt: \"{state['current_task']}\". Falls die "
        f"ursprüngliche Nachricht weitere Anliegen enthält, werden diese "
        f"separat behandelt - gehe NICHT darauf ein, auch nicht kurz erwähnend."
    )

    if results:
        docs_context = "\n".join(
            f"- {r['title']}: {r.get('summary', '')}" for r in results
        )
        system_prompt += (
            f"\n\nGefundene relevante Inhalte aus Knowledge Hub/Intranet:\n"
            f"{docs_context}\nNutze diese als Grundlage für deine Antwort, "
            f"erfinde keine Details, die dort nicht stehen. Nenne am Ende "
            f"deiner Antwort explizit, aus welchem Dokument/Artikel die "
            f"Information stammt (Titel nennen, z.B. \"(Quelle: [Titel])\"), "
            f"damit die Nutzer:in die Angabe selbst nachlesen kann."
        )
    else:
        system_prompt += (
            "\n\nEs wurden keine passenden Dokumente gefunden. Erkläre das "
            "ehrlich, statt zu improvisieren."
        )

    if state.get("pruefer_issues"):
        system_prompt += (
            "\n\nDeine letzte Antwort wurde beanstandet: "
            + "; ".join(state["pruefer_issues"])
            + ". Bitte korrigiere das in deiner nächsten Antwort."
        )

    call_messages = _messages_ending_with_user(
        state["messages"],
        f"Bitte kümmere dich jetzt um diesen Teilschritt: {state['current_task']}",
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=system_prompt,
        messages=call_messages,
    )
    # NICHT direkt an state["messages"] anhängen - erst nach Prüfer-Freigabe
    # (siehe pruefer_node und infrastructure_agent_node, gleiches Prinzip).
    state["draft_response"] = response.content[0].text

    # info_agent schlägt i.d.R. keine Tool-Aktion vor - reine
    # Informationsantwort, kein Bestätigungsschritt nötig.
    state["pending_action"] = None
    return state


# ---------------------------------------------------------------------------
# Scheduling-Agent: Kalendertermine, nach demselben Muster wie
# infrastructure_agent_node (Entwurf + strukturierte Aktions-Extraktion).
# ---------------------------------------------------------------------------

def scheduling_agent_node(state: OnboardingState) -> OnboardingState:
    system_prompt = build_system_prompt(state["transparency_level"])

    system_prompt += (
        f"\n\nWICHTIG: Kümmere dich in dieser Antwort AUSSCHLIESSLICH um "
        f"folgenden Teilschritt: \"{state['current_task']}\". Falls die "
        f"ursprüngliche Nachricht weitere Anliegen enthält, werden diese "
        f"separat behandelt - gehe NICHT darauf ein, auch nicht kurz erwähnend."
    )

    if state.get("pruefer_issues"):
        system_prompt += (
            "\n\nDeine letzte Antwort wurde beanstandet: "
            + "; ".join(state["pruefer_issues"])
            + ". Bitte korrigiere das in deiner nächsten Antwort."
        )

    # 1. Antwort-Entwurf generieren (siehe infrastructure_agent_node für die
    # Begründung von _messages_ending_with_user hier).
    call_messages = _messages_ending_with_user(
        state["messages"],
        f"Bitte kümmere dich jetzt um diesen Teilschritt: {state['current_task']}",
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=system_prompt,
        messages=call_messages,
    )
    # NICHT direkt an state["messages"] anhängen - erst nach Prüfer-Freigabe
    # (siehe pruefer_node, gleiches Prinzip wie bei den anderen Sub-Agenten).
    state["draft_response"] = response.content[0].text

    # 2. Strukturierte Aktions-Extraktion per Tool Use - analog
    # infrastructure_agent_node, nur mit dem Kalender-Tool-Schema.
    extraction_messages = call_messages + [
        {"role": "assistant", "content": state["draft_response"]},
        {"role": "user", "content": "Bewerte anhand des bisherigen Gesprächs: ist ein Kalendertermin nötig?"},
    ]
    extraction_response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        system=(
            "Entscheide anhand der Konversation, ob ein Kalendertermin für die "
            "aktuelle Anfrage vorgeschlagen werden soll."
        ),
        messages=extraction_messages,
        tools=[PROPOSE_CALENDAR_EVENT_TOOL],
        tool_choice={"type": "tool", "name": "propose_calendar_event"},
    )
    action_data = _extract_tool_input(extraction_response, "propose_calendar_event")

    if action_data.get("needed"):
        state["pending_action"] = {
            "tool": "add_calendar_event",
            "args": {
                "date": action_data.get("date", ""),
                "time": action_data.get("time", ""),
                "title": action_data.get("title", "Termin"),
                "organizer": action_data.get("organizer", "Lumi"),
            },
            "reason": action_data.get("reason", ""),
            "department": None,
            # Feste Policy statt Modelleinschätzung, siehe criticality_policy.py -
            # Kalendertermine sind dort als nicht kritisch eingestuft, anders
            # als create_ticket.
            "is_critical": is_tool_critical("add_calendar_event"),
        }
    else:
        state["pending_action"] = None

    return state


def pruefer_node(state: OnboardingState) -> OnboardingState:
    last_response = state.get("draft_response", "")
    issues = []

    is_critical = (state.get("pending_action") or {}).get("is_critical", False)
    if is_critical and "%" in last_response:
        issues.append("Konfidenzwert bei kritischer Aussage verwendet (L2 verletzt)")

    lowered = last_response.lower()
    if any(phrase in lowered for phrase in GENERIC_PHRASES):
        issues.append("generische Floskel statt konkreter Begründung (L3 verletzt)")

    state["pruefer_issues"] = issues
    state["pruefer_verdict"] = "beanstandung" if issues else "freigabe"

    if state["pruefer_verdict"] == "freigabe":
        # Erst JETZT wird der Entwurf Teil der sichtbaren, permanenten
        # Historie - abgelehnte Entwürfe (Korrekturschleife) haben es nie
        # bis hierher geschafft und bleiben unsichtbar für die Nutzer:in.
        state["messages"].append({"role": "assistant", "content": state["draft_response"]})

    log_interaction(
        category="pruefer_check",
        node="pruefer",
        session_id=state["session_id"],
        task=state.get("current_task"),
        channel=state["channel"],
        verdict=state["pruefer_verdict"],
        issues=issues,
    )
    return state


def route_from_pruefer(state: OnboardingState) -> str:
    if state["pruefer_verdict"] == "beanstandung":
        state["check_target"] = "correction"
        return "supervisor"
    return "context_check"


# ---------------------------------------------------------------------------
# Kontext-Check (G13): Zustand bei Zustimmung vs. jetzt
# ---------------------------------------------------------------------------

def _snapshot_relevant_state(sandbox_state: dict, pending_action: dict) -> dict:
    """Nimmt nur den für die geplante Aktion relevanten Ausschnitt des
    Sandbox-Zustands auf - nicht den kompletten State (der würde sich
    durch unabhängige Dinge ständig "ändern")."""
    return {
        "tickets_count": len(sandbox_state.get("tickets", [])),
        "department": pending_action.get("department"),
    }


def context_check_node(state: OnboardingState) -> OnboardingState:
    """Nimmt NUR den Baseline-Snapshot für den G13-Vergleich auf - der
    eigentliche Vergleich (Snapshot bei Zustimmung vs. Zustand direkt vor
    der Ausführung) passiert jetzt in context_recheck_node, NACH der
    ersten Bestätigung in human_review_node.

    Früher gab es hier auch schon einen Vergleich (elif previous !=
    current). Der ist entfernt: previous (state["pending_action_snapshot"])
    war an DIESER Stelle strukturell IMMER None, denn context_check_node
    läuft synchron direkt nach der Prüfer-Freigabe, bevor irgendein
    interrupt() überhaupt eine Wartezeit ermöglicht hätte, in der sich
    etwas hätte ändern können - UND pending_action_snapshot wird pro
    Teilschritt zurückgesetzt (siehe supervisor_node,
    check_target=="next_subtask"). Ein "previous is not None" hier kam nur
    durch einen Bug zustande (Snapshot eines VORHERIGEN Teilschritts blieb
    stehen) - kein echter G13-Fall, siehe Bericht an die Nutzerin."""
    action = state.get("pending_action")
    if action is None:
        state["context_changed"] = False
        # Kein Replay-Risiko hier (kein interrupt() in diesem Knoten) -
        # läuft pro Checkpoint-Schritt genau einmal, kein Dedup nötig.
        log_interaction(
            category="context_check", node="context_check",
            session_id=state["session_id"], task=state.get("current_task"),
            channel=state["channel"], context_changed=False,
        )
        return state

    state["pending_action_snapshot"] = _snapshot_relevant_state(state["sandbox_state"], action)
    state["context_changed"] = False

    log_interaction(
        category="context_check", node="context_check",
        session_id=state["session_id"], task=state.get("current_task"),
        channel=state["channel"], context_changed=False,
    )
    return state


def route_from_context_check(state: OnboardingState) -> str:
    return "updated_query" if state["context_changed"] else "human_review"


def _human_review_needs_interrupt(state: OnboardingState) -> bool:
    """Zentrale Bedingung für 'nimmt human_review_node den autonomen Zweig
    (ohne interrupt()) oder wartet es auf eine Bestätigung' - von
    human_review_node UND announce_confirmation_node genutzt, statt an
    beiden Stellen denselben Ausdruck zu wiederholen.

    control_level == "low"    -> nie bestätigen (voll autonom)
    control_level == "medium" -> nur bestätigen, wenn is_critical (siehe
                                  criticality_policy.py) - Studienbedingung,
                                  siehe DEFAULT_CONTROL_LEVEL in api/config.py
    control_level == "high"   -> immer bestätigen, auch unkritische Aktionen
    Kein pending_action -> nichts zu bestätigen, unabhängig von control_level."""
    action = state["pending_action"]
    if action is None:
        return False
    control_level = state["control_level"]
    if control_level == "low":
        return False
    if control_level == "medium":
        # Im Zweifel bestätigen lassen statt stillschweigend autonom
        # durchlaufen zu lassen - dieselbe Vorsichtsregel wie im Default von
        # criticality_policy.is_tool_critical().
        return action.get("is_critical", True)
    return True  # "high"


def announce_confirmation_node(state: OnboardingState) -> OnboardingState:
    """Sitzt zwischen context_check und human_review/updated_query, NUR um
    den 'interrupt_raised'-Log-Eintrag GENAU EINMAL zu schreiben, bevor der
    eigentliche interrupt()-Aufruf im Nachfolgeknoten passiert - siehe
    Bericht an die Nutzerin: ein Dedup-Versuch ÜBER dot_status INNERHALB
    des interrupt()-Knotens selbst schlug fehl, weil ein raisender
    interrupt()-Aufruf die vorherigen state-Mutationen desselben
    Knotendurchlaufs nicht checkpointet - der Resume-Durchlauf sah wieder
    den alten Stand und loggte ein zweites Mal. Dieser Knoten hier dagegen
    schließt VOR dem interrupt() regulär als eigener Graph-Schritt ab, wird
    also genau einmal checkpointet; ein Resume läuft nie erneut durch ihn.

    Loggt NICHT bedingungslos: updated_query_node interrupt't immer,
    sobald es erreicht wird (kein autonomer Zweig dort). human_review_node
    dagegen nimmt in mehreren Fällen den autonomen Zweig OHNE interrupt()
    (siehe _human_review_needs_interrupt: control_level=="low", kein
    pending_action, oder control_level=="medium" mit is_critical==False) -
    für die würde ein unbedingtes Log hier eine Bestätigung ankündigen, die
    nie erscheint. Die Unterscheidung nutzt _human_review_needs_interrupt()
    (dieselbe Funktion, die auch human_review_node selbst verwendet) statt
    die Bedingung hier zu wiederholen, und ermittelt das Ziel über
    route_from_context_check() (dieselbe Funktion, die auch als
    Routing-Bedingung in build_graph() hängt) statt eine zweite
    Routing-Logik zu bauen."""
    target_node = route_from_context_check(state)
    if target_node == "human_review" and not _human_review_needs_interrupt(state):
        return state

    log_interaction(
        category="interrupt_raised",
        node=target_node,
        session_id=state["session_id"],
        task=state.get("current_task"),
        channel=state["channel"],
        proposal=state.get("pending_action"),
        change_notice=state.get("change_description") if target_node == "updated_query" else None,
    )
    return state


# ---------------------------------------------------------------------------
# Aktualisierte Nachfrage bei geändertem Kontext (Punkt 5)
# ---------------------------------------------------------------------------

def updated_query_node(state: OnboardingState) -> OnboardingState:
    # Der "interrupt_raised"-Log-Eintrag für diesen Fall entsteht bereits
    # VORHER in announce_confirmation_node, nicht hier - ein raisender
    # interrupt()-Aufruf checkpointet keine state-Mutationen aus demselben
    # Knotendurchlauf, die davor gemacht wurden (siehe dortiger
    # Docstring), ein log_interaction() an dieser Stelle würde also bei
    # jedem Resume ein zweites Mal laufen.
    state["dot_status"] = "waiting"
    decision = interrupt({
        "proposal": state["pending_action"],
        "change_notice": state.get("change_description"),
        "options": ["trotzdem bestätigen", "abbrechen"],
    })
    log_interaction(
        category="confirm",
        node="updated_query",
        session_id=state["session_id"],
        task=state.get("current_task"),
        channel=state["channel"],
        decision=decision,
        context_changed=True,
    )
    if decision != "trotzdem bestätigen":
        state["pending_action"] = None
    state["dot_status"] = "idle"
    return state


def route_from_updated_query(state: OnboardingState) -> str:
    return "execute_action" if state["pending_action"] else "__end__"


# ---------------------------------------------------------------------------
# Human Review (unveränderter Kontext)
# ---------------------------------------------------------------------------

def human_review_node(state: OnboardingState) -> OnboardingState:
    if not _human_review_needs_interrupt(state):
        log_interaction(
            category="autonomous", node="human_review",
            session_id=state["session_id"], task=state.get("current_task"),
            channel=state["channel"],
        )
        return state

    # Der "interrupt_raised"-Log-Eintrag für diesen Fall entsteht bereits
    # VORHER in announce_confirmation_node, nicht hier - siehe identischer
    # Kommentar in updated_query_node.
    state["dot_status"] = "waiting"
    decision = interrupt({
        "proposal": state["pending_action"],
        "options": ["bestätigen", "anpassen", "ablehnen"],
    })
    log_interaction(
        category="confirm", node="human_review",
        session_id=state["session_id"], task=state.get("current_task"),
        channel=state["channel"], decision=decision,
    )
    if decision != "bestätigen":
        state["pending_action"] = None
    state["dot_status"] = "idle"
    return state


# ---------------------------------------------------------------------------
# G13, zweiter Vergleich: Zustand bei Zustimmung vs. Zustand direkt vor der
# Ausführung - läuft NACH der ersten Bestätigung, VOR execute_action.
# ---------------------------------------------------------------------------

def context_recheck_node(state: OnboardingState) -> OnboardingState:
    """Der eigentliche G13-Vergleich (siehe context_check_node): vergleicht
    den Snapshot bei Zustimmung (state["pending_action_snapshot"]) gegen
    den LIVE-Zustand direkt vor der Ausführung. Läuft NACH der ersten
    Bestätigung in human_review_node (bzw. nach dessen autonomem Zweig),
    NICHT davor - das ist der einzige Punkt in diesem Graphen, an dem
    zwischen Snapshot-Zeitpunkt und Vergleichs-Zeitpunkt überhaupt eine
    Wartezeit (der erste interrupt()) gelegen haben kann, in der sich
    etwas hätte ändern können.

    KEIN eigener interrupt() hier - läuft deshalb garantiert nur einmal
    (kein Replay-Risiko, gleiches Prinzip wie announce_confirmation_node).
    Bei erkannter Änderung wird zum bestehenden updated_query_node
    geroutet, das die zweite Bestätigung ("trotzdem bestätigen"/
    "abbrechen") tatsächlich einholt, BEVOR execute_action läuft
    (Guideline 6: Rückmeldung VOR Ausführung, nicht danach - die Person
    muss die Zustimmung zurückziehen können, nachdem sie von der Änderung
    erfährt).

    WICHTIG (siehe Bericht an die Nutzerin): sandbox_state ändert sich im
    aktuellen, streng sequenziellen Ausführungsmodell NICHT von selbst
    während ein interrupt() wartet - dieser Knoten macht den Vergleich
    strukturell korrekt, löst ihn aber im laufenden Betrieb nur dann aus,
    wenn etwas AUSSERHALB dieses einen Graph-Laufs sandbox_state ändert
    (z.B. über graph.update_state() - siehe test_context_recheck.py). Ohne
    einen Sync-Kanal zwischen Sandbox-UI und sandbox_state ist das im
    Studienbetrieb aktuell nicht durch echte Nutzeraktionen erreichbar
    (siehe Setup_Dokumentation.md)."""
    action = state.get("pending_action")
    if action is None:
        # 'ablehnen'/'anpassen' in human_review_node hat pending_action
        # bereits auf None gesetzt - nichts zu vergleichen.
        state["context_changed"] = False
        return state

    current = _snapshot_relevant_state(state["sandbox_state"], action)
    previous = state.get("pending_action_snapshot")

    if previous is not None and previous != current:
        state["context_changed"] = True
        state["change_description"] = (
            f"Es gibt inzwischen {current['tickets_count']} statt vorher "
            f"{previous['tickets_count']} offene Tickets."
        )
        # interrupt_raised-Log für den ZWEITEN Interrupt (updated_query)
        # direkt hier, nicht über announce_confirmation_node - dieser
        # Knoten ist (wie announce_confirmation_node) der einzige
        # Vorgänger, der diese zweite Bestätigung auslöst, läuft
        # garantiert nur einmal, und route_from_context_check ist hier
        # nicht wiederverwendbar (anderes "unverändert"-Ziel:
        # execute_action statt human_review) - eigene, kleine
        # Routing-Entscheidung statt Nachbau der bestehenden unter
        # anderem Namen.
        log_interaction(
            category="interrupt_raised", node="updated_query",
            session_id=state["session_id"], task=state.get("current_task"),
            channel=state["channel"], proposal=action,
            change_notice=state["change_description"],
        )
    else:
        state["context_changed"] = False
    return state


def route_from_context_recheck(state: OnboardingState) -> str:
    return "updated_query" if state["context_changed"] else "execute_action"


# ---------------------------------------------------------------------------
# Eskalation - mit Abbruchgrund + Alternative/menschlichem Kontakt (Punkt 2)
# ---------------------------------------------------------------------------

def escalate_node(state: OnboardingState) -> OnboardingState:
    colleague = find_colleague_for_topic(state.get("current_task", ""))
    # Additiv fürs Rationale-Feld der API-Schicht (siehe backend/api/rationale.py) -
    # rein informativ, wird von keinem anderen Knoten/Routing gelesen.
    state["last_colleague"] = colleague

    if state.get("correction_count", 0) > MAX_CORRECTION_ATTEMPTS:
        reason = "; ".join(state.get("pruefer_issues", [])) or "wiederholte Qualitätsprobleme"
        if colleague:
            instruction = (
                f"Erkläre freundlich, dass die Anfrage nach mehreren Versuchen nicht "
                f"zuverlässig bearbeitet werden konnte (Grund: {reason}), und verweise "
                f"konkret auf {colleague['name']} ({colleague['department']}) als "
                f"Ansprechperson."
            )
        else:
            instruction = (
                f"Erkläre freundlich, dass die Anfrage nach mehreren Versuchen nicht "
                f"zuverlässig bearbeitet werden konnte (Grund: {reason}), und bitte darum, "
                f"stattdessen ein Ticket für menschliche Unterstützung zu erstellen."
            )
    else:
        colleague_hint = (
            f"Verweise konkret auf {colleague['name']} ({colleague['department']}) als "
            f"zuständige Person für dieses Thema."
            if colleague
            else "Erkläre, dass dafür aktuell kein spezifischer Kontakt bekannt ist."
        )
        instruction = ESCALATION_PROMPT + "\n\n" + colleague_hint

    # Fokus-Anweisung, wie beim Infrastructure-Agenten: nur den aktuellen
    # Teilschritt ansprechen, bereits behandelte Themen nicht wiederholen.
    instruction += (
        f"\n\nWICHTIG: Es geht in dieser Antwort AUSSCHLIESSLICH um folgenden "
        f"Teilschritt: \"{state.get('current_task', '')}\". Andere Anliegen aus "
        f"der ursprünglichen Nachricht wurden bereits separat behandelt oder "
        f"werden noch behandelt - erwähne sie NICHT erneut, auch nicht kurz."
    )

    # Echter LLM-Aufruf statt wörtlicher Ausgabe der Anweisung. Eigene
    # Nachrichtenliste mit User-Abschluss (siehe infrastructure_agent_node -
    # dieselbe API-Anforderung: Konversation muss mit "user" enden).
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        system=instruction,
        messages=state["messages"] + [
            {"role": "user", "content": "Bitte formuliere jetzt die Antwort an die Nutzer:in."}
        ],
    )
    state["messages"].append({"role": "assistant", "content": response.content[0].text})

    log_interaction(
        category="escalate", node="escalate",
        session_id=state["session_id"], channel=state["channel"],
        correction_exhausted=state.get("correction_count", 0) > MAX_CORRECTION_ATTEMPTS,
    )
    state["dot_status"] = "idle"
    state["check_target"] = "next_subtask"
    return state


def _execution_confirmation_text(action: dict) -> str:
    """Kurzer, deterministischer Bestätigungstext (bewusst KEIN LLM-Aufruf -
    reine Nennung der tatsächlich ausgeführten Aktion aus `action`, nicht
    generisch). Siehe execute_action_node."""
    tool = action.get("tool")
    args = action.get("args") or {}

    if tool == "create_ticket":
        department = action.get("department") or args.get("department")
        if department:
            return f"Erledigt – das Ticket ist bei {department} angelegt."
        return "Erledigt – das Ticket ist angelegt."

    if tool == "add_calendar_event":
        title = args.get("title")
        if title:
            return f"Erledigt – „{title}“ ist im Kalender eingetragen."
        return "Erledigt – der Termin ist eingetragen."

    if tool == "send_message":
        to = args.get("to")
        if to:
            return f"Erledigt – die Nachricht an {to} ist raus."
        return "Erledigt – die Nachricht ist gesendet."

    return "Erledigt."


def execute_action_node(state: OnboardingState) -> OnboardingState:
    action = state["pending_action"]
    if action:
        tool_fn = AVAILABLE_TOOLS[action["tool"]]
        tool_fn(state["sandbox_state"], **action["args"])
        # Sichtbare Rückmeldung im Chat, dass die bestätigte Aktion
        # tatsächlich gewirkt hat - vorher passierte nach der Bestätigung
        # nichts Sichtbares (siehe Architektur-Gespräch, erlebte Kontrolle).
        state["messages"].append(
            {"role": "assistant", "content": _execution_confirmation_text(action)}
        )
        # Additiv fürs Rationale-Feld der API-Schicht (siehe
        # backend/api/rationale.py): pending_action wird direkt im Anschluss
        # auf None zurückgesetzt, daher hier separat für den
        # "...erstellt/eingetragen/gesendet"-Schritt der obigen
        # Bestätigungsnachricht festgehalten.
        state["last_executed_action"] = action
    state["pending_action"] = None
    state["dot_status"] = "idle"
    # Zurück zum Supervisor statt direkt zu enden - prüft dort, ob es
    # weitere Teilschritte aus der Zerlegung gibt (mehrere Anliegen in
    # einer Nachricht).
    state["check_target"] = "next_subtask"
    return state


# ---------------------------------------------------------------------------
# Graph zusammensetzen
# ---------------------------------------------------------------------------

def build_graph(checkpointer=None):
    graph = StateGraph(OnboardingState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("infrastructure_agent", infrastructure_agent_node)
    graph.add_node("info_agent", info_agent_node)
    graph.add_node("scheduling_agent", scheduling_agent_node)
    graph.add_node("pruefer", pruefer_node)
    graph.add_node("context_check", context_check_node)
    graph.add_node("announce_confirmation", announce_confirmation_node)
    graph.add_node("updated_query", updated_query_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("context_recheck", context_recheck_node)
    graph.add_node("escalate", escalate_node)
    graph.add_node("execute_action", execute_action_node)

    graph.set_entry_point("supervisor")
    graph.add_conditional_edges("supervisor", route_from_supervisor, {
        "infrastructure_agent": "infrastructure_agent",
        "info_agent": "info_agent",
        "scheduling_agent": "scheduling_agent",
        "escalate": "escalate",
        "__end__": END,
    })

    graph.add_edge("infrastructure_agent", "pruefer")
    graph.add_edge("info_agent", "pruefer")
    graph.add_edge("scheduling_agent", "pruefer")
    graph.add_conditional_edges("pruefer", route_from_pruefer, {
        "supervisor": "supervisor",
        "context_check": "context_check",
    })

    # context_check -> announce_confirmation ist eine EINFACHE Kante (kein
    # eigenes Routing) - announce_confirmation entscheidet selbst per
    # route_from_context_check() weiter, siehe dortiger Docstring.
    graph.add_edge("context_check", "announce_confirmation")
    graph.add_conditional_edges("announce_confirmation", route_from_context_check, {
        "updated_query": "updated_query",
        "human_review": "human_review",
    })

    graph.add_conditional_edges("updated_query", route_from_updated_query, {
        "execute_action": "execute_action",
        "__end__": END,
    })

    # human_review -> context_recheck statt direkt -> execute_action: der
    # zweite G13-Vergleich (siehe context_recheck_node) muss zwischen jeder
    # ersten Bestätigung/jedem autonomen Durchlauf und der tatsächlichen
    # Ausführung liegen, sonst käme eine erkannte Änderung erst NACH der
    # Ausführung ans Licht (Guideline 6 verlangt VORHER).
    graph.add_edge("human_review", "context_recheck")
    graph.add_conditional_edges("context_recheck", route_from_context_recheck, {
        "updated_query": "updated_query",
        "execute_action": "execute_action",
    })

    # Beide führen zurück zum Supervisor (dort: check_target="next_subtask"),
    # statt die gesamte Kette nach einem einzigen Teilschritt zu beenden.
    graph.add_edge("execute_action", "supervisor")
    graph.add_edge("escalate", "supervisor")

    # Checkpointer wird vom Aufrufer übergeben (siehe test_graph.py) - muss
    # als "with SqliteSaver.from_conn_string(...) as checkpointer:" über die
    # GESAMTE Testlauf-Dauer offen gehalten werden, da from_conn_string in
    # aktuellen langgraph-Versionen ein Context-Manager ist, kein direktes
    # Objekt. build_graph() erzeugt ihn deshalb bewusst NICHT mehr selbst.
    return graph.compile(checkpointer=checkpointer)
