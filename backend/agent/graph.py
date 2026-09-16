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

import datetime
import re

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
from .text_matching import tokenize, any_word_matches

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MAX_CORRECTION_ATTEMPTS = 2

# Bewusst schlanke, leicht erweiter-/kürzbare Liste - Guidelines sind noch
# nicht final. Nicht sinnvoll prüfbare Punkte fliegen raus statt erzwungen
# zu werden (siehe Architektur-Gespräch, Punkt 3).
GENERIC_PHRASES = ["aus verschiedenen gründen", "wie du sicher weißt", "generell gilt"]

# ---------------------------------------------------------------------------
# Gemeinsamer Fähigkeiten-Baustein (siehe Bericht an die Nutzerin) - ERSETZT
# die früher drei separaten "WICHTIG ZUR EIGENEN ROLLE"-Blöcke in
# infrastructure_agent_node/scheduling_agent_node/info_agent_node. Grund für
# den Umbau: jeder Knoten kannte bisher nur SEINE EIGENE Fähigkeit, keiner
# hatte ein vollständiges Bild - das führte wiederholt dazu, dass Lumi sich
# selbst kleinredete, wenn der "falsche" Knoten eine Anfrage bearbeitete
# (z.B. info_agent bei einer Ticket-Bitte, ohne vom Ticket-Tool zu wissen).
# Jetzt EINE Quelle, von JEDEM Knoten inkl. Supervisor genutzt (der bekommt
# dadurch zum ersten Mal überhaupt einen system-Prompt bei der Zerlegung).
#
# Nur Tools, die über einen echten Graph-Pfad tatsächlich erreichbar sind -
# siehe rationale.py für die Tools, die zwar in AVAILABLE_TOOLS (tools.py)
# stehen, aber von keinem Knoten aufgerufen werden (send_message,
# create/update_onboarding_plan) - die gehören NICHT hier rein, sonst
# behauptet Lumi wieder eine Fähigkeit, die kein Codepfad einlöst.
#
# WICHTIG bei künftigen Änderungen: wird eine neue Aktion erreichbar (z.B.
# der HR-Ticket-Pfad), MUSS dieser Baustein hier mit aktualisiert werden -
# er ist die einzige Quelle, kein Duplikat woanders.
LUMI_CAPABILITIES = (
    "Das kannst du als Lumi tatsächlich selbst bewirken, nicht nur "
    "beschreiben: Ein IT-Ticket anlegen (aktuell nur bei der IT-Abteilung) "
    "- für Zugänge, Hardware, Software. Einen Termin im Kalender eintragen "
    "- nur innerhalb der aktuell angezeigten Woche (Montag bis Freitag). "
    "Die Wissensdatenbank (Knowledge Hub) und das Intranet durchsuchen und "
    "gefundene Inhalte wiedergeben.\n\n"
    "Das kannst du NICHT selbst: alles außerhalb dieser drei Aktionen - "
    "dafür gibt es die Eskalation an eine echte Person, keine "
    "Selbsthilfe-Anleitung und keinen erfundenen externen Weg (keine "
    "E-Mail-Adressen, keine Telefonnummern, keine externen Portale - die "
    "Sandbox kennt nur fünf Apps: Chat, Intranet, Knowledge Hub, Tickets, "
    "Kalender).\n\n"
    "Behaupte nie, eine der drei Aktionen oben nicht zu können, nur weil "
    "du selbst (als der gerade zuständige Teil des Systems) sie in diesem "
    "Moment nicht ausführst - eine andere Stelle im System kann dafür "
    "zuständig sein. Biete umgekehrt auch nichts an, wofür es hier keine "
    "der drei Aktionen gibt."
)


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
                            # Bugfix (siehe Bericht an die Nutzerin): vorher rein
                            # themenbasiert ("Urlaub" stand als Beispiel wörtlich
                            # unter 'info', "Zugänge" unter 'infrastructure') -
                            # das ließ eine Handlungsanfrage und eine Erklärfrage
                            # zum selben Thema in dieselbe Kategorie fallen, obwohl
                            # nur EINE davon einen handlungsfähigen Knoten hinter
                            # sich hat. Jetzt Absicht ZUERST, Thema danach, plus
                            # Beispielpaare direkt im Schema (few-shot-Anker,
                            # zuverlässiger als Prosa allein) - siehe auch
                            # criticality_policy.py: dieselbe Lehre ("Absicht
                            # nicht am Thema ablesen"), hier als Formulierung statt
                            # als feste Tabelle, weil eine Zerlegung in einen von
                            # vier Werten ein enger gefasster, erzwungener
                            # Tool-Use ist als freie Textgenerierung.
                            #
                            # Bugfix, zweite Runde (siehe Bericht an die
                            # Nutzerin): "Absicht ZUERST" allein reichte nicht -
                            # eine Gehaltsfrage ist formal eine Auskunftsfrage und
                            # landete dadurch bei 'info', obwohl das Thema
                            # überhaupt nicht in Lumis Zuständigkeit liegt (keine
                            # Eskalation, info_agent sucht ins Leere). Absicht
                            # (Frage vs. Handlung) und Zuständigkeit (gehört das
                            # Thema überhaupt zu den drei Bereichen) sind zwei
                            # UNABHÄNGIGE Achsen - Zuständigkeit muss deshalb VOR
                            # Absicht geprüft werden, sonst rettet die Frageform
                            # ein eigentlich zuständigkeitsfremdes Thema nach
                            # 'info'.
                            "description": (
                                "Entscheide in ZWEI Schritten. SCHRITT 1 "
                                "(Zuständigkeit, geht IMMER vor der Absichtsart): "
                                "Liegt das Thema überhaupt in Lumis Bereich - "
                                "Zugänge/Hardware/Software, Kalendertermine, oder "
                                "allgemeine Onboarding-/Organisationsthemen "
                                "(Urlaub, Richtlinien, Firmeninfos aus Knowledge "
                                "Hub/Intranet)? Liegt es AUSSERHALB (z.B. Gehalt, "
                                "Vertragsdetails, persönliche HR-Themen, alles "
                                "ohne Bezug zu diesen Bereichen), ist es IMMER "
                                "'other' - auch wenn die Nachricht als Frage oder "
                                "Auskunftswunsch formuliert ist. Eine Frageform "
                                "allein macht ein Thema nicht zuständig. SCHRITT 2 "
                                "(nur innerhalb der Zuständigkeit aus Schritt 1): "
                                "entscheide nach Absicht, danach nach Thema: "
                                "'infrastructure' = eine KONKRETE AKTION zu "
                                "Zugängen/Hardware/Software wird verlangt (z.B. "
                                "'richte mir X ein', 'ich brauche Zugang zu Y', "
                                "'kannst du das einrichten') - NICHT allgemeine "
                                "Erklärungen, wie oder warum etwas funktioniert. "
                                "'info' = eine ERKLÄRUNG oder Auskunft wird "
                                "verlangt, UND das Thema liegt laut Schritt 1 in "
                                "Lumis Zuständigkeit, WENN keine konkrete Aktion "
                                "verlangt wird (z.B. 'wie funktioniert VPN hier?', "
                                "'was ist die Urlaubsregelung?', allgemein: "
                                "Urlaub, Richtlinien, Onboarding-Themen). "
                                "'scheduling' = ein KONKRETER Termin soll "
                                "eingetragen oder geändert werden (z.B. 'trag mir "
                                "X ein', NICHT 'wie voll ist mein Kalender diese "
                                "Woche'). "
                                "'other' = außerhalb dieser drei Zuständigkeiten "
                                "(siehe Schritt 1) oder unklare Absicht. "
                                "Beispielpaar Zugänge: 'Richte mir VPN-Zugang ein' "
                                "-> infrastructure. 'Wie funktioniert der "
                                "VPN-Zugang hier?' -> info. "
                                "Beispielpaar Kalender: 'Trag ein Meeting am "
                                "Montag ein' -> scheduling. 'Was steht diese "
                                "Woche in meinem Kalender?' -> info. "
                                "Beispielpaar Zuständigkeit (Schritt 1, BEIDE "
                                "Auskunftsfragen - entscheidend ist hier NICHT "
                                "die Absicht, sondern ob das Thema überhaupt "
                                "dazugehört): 'Was ist die Urlaubsregelung?' -> "
                                "info (Thema gehört dazu). 'Was verdient ein "
                                "Kollege?' -> other (Thema gehört nicht dazu, "
                                "obwohl genauso als Frage formuliert)."
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
            # Ergänzt (siehe Bericht an die Nutzerin): fehlte im Schema
            # komplett - das Modell erfand dafür einen freien JSON-Block
            # ("context"/"description") im Fließtext, den _strip_structured_
            # tail() jetzt korrekt abschneidet, wodurch die Information
            # aber ganz verschwand, statt an ihren eigentlichen Platz (die
            # Karte) zu wandern. WICHTIGE UNTERSCHEIDUNG zu "reason" unten:
            # description ist AN DEN TICKETEMPFÄNGER (IT) gerichtet, dritte
            # Person ist dort richtig - reason bleibt die Begründung AN DIE
            # NUTZER:IN, zweite Person. Design: grauer Block (inkl. dieses
            # Felds) = was ins Ticket geht, Reasoning-Text darunter = warum,
            # an die Person gerichtet.
            "description": {
                "type": "string",
                "description": (
                    "Der Text, der INS TICKET geht - für die IT als Empfängerin "
                    "geschrieben, dritte Person (z.B. 'Neue Mitarbeiterin benötigt "
                    "einen VPN-Zugang für ihr Mac-Gerät, um auf interne Tools "
                    "zugreifen zu können.'). NICHT mit 'reason' verwechseln: reason "
                    "ist die Begründung AN DIE NUTZER:IN (zweite Person, 'Du'), "
                    "description ist die Problem-/Anliegenbeschreibung FÜR die IT "
                    "(dritte Person)."
                ),
            },
            # Erzwungenes Pflichtfeld statt optional (siehe Bericht an die
            # Nutzerin: dieselbe Begründung wie bei within_current_week -
            # eine diskrete, erzwungene Entscheidung ist zuverlässiger als
            # freie Textgenerierung, die das Feld auch mal wegließe). Die
            # Karte zeigt priority automatisch mit an (generisches Rendern
            # von proposal.args, siehe ConfirmationCard.tsx), OHNE dass der
            # Fließtext es zusätzlich nennen muss.
            "priority": {
                "type": "string",
                "enum": ["niedrig", "normal", "hoch"],
                "description": (
                    "Priorität des Tickets. 'normal' als Default, wenn aus der "
                    "Anfrage nichts anderes hervorgeht - frag NICHT extra danach, "
                    "nur 'niedrig'/'hoch' wählen, wenn die Nutzer:in das "
                    "erkennbar meint (z.B. 'dringend' -> hoch)."
                ),
            },
            # Bugfix (siehe Bericht an die Nutzerin): das Modell formulierte
            # das bisher wie eine Notiz AN den Ticketempfänger, über die
            # Nutzer:in in dritter Person ("Die Nutzer:in hat...") - im
            # Design (ConfirmationCard) ist die Begründung aber direkt AN
            # die Nutzer:in gerichtet ("Du benötigst..."), da die Karte IHR
            # angezeigt wird, nicht der IT. Jetzt explizit vorgegeben.
            "reason": {
                "type": "string",
                "description": (
                    "Kurze Begründung, DIREKT an die Nutzer:in gerichtet (Anrede "
                    "'Du', z.B. 'Du benötigst einen neuen VPN-Zugang, der vom "
                    "IT-Team eingerichtet werden muss.') - NICHT in dritter "
                    "Person über sie ('Die Nutzer:in hat...'), das liest sich wie "
                    "eine interne Notiz an die IT statt wie eine Erklärung an sie."
                ),
            },
        },
        "required": ["needed", "priority", "description"],
    },
}


# 0=Montag ... 4=Freitag - deckungsgleich mit Appointment.day in
# kalenderData.ts (Frontend). Genutzt sowohl im Tool-Schema unten als auch
# in _execution_confirmation_text(), damit die Bestätigungsnachricht den
# tatsächlich eingetragenen (ggf. gerundeten) Wochentag nennt, statt ihn
# stillschweigend zu verschieben (siehe Bericht an die Nutzerin).
WEEKDAY_NAMES = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]

def _sandbox_today_weekday_name() -> str | None:
    """Heutiger Wochentag zur LAUFZEIT ermittelt (datetime.date.today()),
    NICHT fest hinterlegt - siehe Bericht an die Nutzerin: ein fester
    Tag lag irgendwann in der Vergangenheit relativ zum tatsächlichen
    Testzeitpunkt, und "morgen" hätte gegen ein fiktives Datum gerechnet.
    None am Wochenende (Sa/So) - der Mo-Fr-Kalender hat dann kein "heute".

    Bewusst NUR der Wochentags-NAME, kein Kalenderdatum: ein konkretes
    Datum ("heute ist der 23.09.2026") hat das Modell in einem echten
    Testlauf dazu verleitet, Kalenderdaten zu VERGLEICHEN ("Dienstag,
    22.09. liegt vor dem 23.09., also schon vorbei, muss übernächste
    Woche gemeint sein") statt den genannten Wochentag einfach auf das
    Sandbox-Raster abzubilden - das Sandbox-"Vorher/Nachher" existiert
    nicht, es gibt nur EINE Woche, jeder genannte Wochentag darin ist
    gültig, unabhängig vom heutigen Wochentag."""
    weekday = datetime.date.today().weekday()  # 0=Montag ... 6=Sonntag
    if weekday > 4:
        return None
    return WEEKDAY_NAMES[weekday]


def _sandbox_today_instruction() -> str:
    """Textbaustein für den System-Prompt (draft response UND Extraktion,
    siehe scheduling_agent_node) - siehe _sandbox_today_weekday_name()."""
    today_name = _sandbox_today_weekday_name()
    if today_name is not None:
        return (
            f"Heutiger Wochentag in dieser Sandbox-Umgebung: {today_name}. Nutze "
            f"NUR den Wochentagsnamen, um relative Zeitangaben ('morgen', "
            f"'übermorgen') aufzulösen. WICHTIG: Vergleiche dabei KEINE "
            f"Kalenderdaten und urteile NICHT, ob ein genannter Wochentag 'schon "
            f"vorbei' ist - jeder genannte Wochentag (Montag bis Freitag) bezieht "
            f"sich auf DIESE eine angezeigte Woche, unabhängig davon, ob er vor "
            f"oder nach dem heutigen Wochentag liegt."
        )
    return (
        "Heute ist Wochenende - der Sandbox-Kalender kennt nur Werktage (Montag "
        "bis Freitag) und hat deshalb gerade kein 'heute'. Bei relativen "
        "Zeitangaben ('heute', 'morgen', 'übermorgen') kannst du das gerade "
        "nicht auflösen - erkläre das der Nutzer:in ehrlich (Wochenende, kein "
        "'heute' im Kalender), statt zu raten. Nennt die Nutzer:in stattdessen "
        "einen konkreten Wochentag (Montag bis Freitag), trage das ganz normal ein."
    )


PROPOSE_CALENDAR_EVENT_TOOL = {
    "name": "propose_calendar_event",
    "description": (
        "Entscheidet, ob für die aktuelle Anfrage ein Kalendertermin vorgeschlagen "
        "werden soll, und normalisiert Wochentag/Uhrzeit auf das Raster der Sandbox "
        "(nur die aktuelle Woche, Montag bis Freitag, volle Stunden 8-16 Uhr - siehe "
        "within_current_week)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "needed": {
                "type": "boolean",
                "description": "Ob überhaupt ein Termin für diese Anfrage nötig ist",
            },
            "within_current_week": {
                "type": "boolean",
                "description": (
                    "Ob sich der genannte Zeitpunkt auf einen Werktag (Montag bis "
                    "Freitag) der AKTUELLEN Woche bezieht. false, wenn ein anderer "
                    "Zeitraum gemeint ist (z.B. 'nächste Woche', 'in drei Wochen', "
                    "'nächsten Monat') oder ein Samstag/Sonntag - der Sandbox-Kalender "
                    "zeigt in diesem Prototyp nur eine einzelne Woche. Bei false "
                    "werden weekday/hour nicht verwendet, needed kann trotzdem true sein."
                ),
            },
            "weekday": {
                "type": "integer",
                "enum": [0, 1, 2, 3, 4],
                "description": (
                    "Wochentag als Index: 0=Montag, 1=Dienstag, 2=Mittwoch, "
                    "3=Donnerstag, 4=Freitag. Nur relevant, wenn within_current_week "
                    "true ist. Beispiel: 'Donnerstag' -> 3."
                ),
            },
            "hour": {
                "type": "integer",
                "enum": [8, 9, 10, 11, 12, 13, 14, 15, 16],
                "description": (
                    "Uhrzeit als volle Stunde im 24-Stunden-Format, auf die "
                    "nächstgelegene darstellbare Stunde gerundet (der Sandbox-Kalender "
                    "kennt keine Minuten). Beispiele: '14:00' -> 14, 'halb drei "
                    "nachmittags' (14:30) -> 14 oder 15 (nächstgelegene volle Stunde), "
                    "'morgens um 9' -> 9. Nur relevant, wenn within_current_week true ist."
                ),
            },
            "title": {"type": "string", "description": "Kurzer Titel des Termins"},
            "location": {
                "type": "string",
                "description": "Ort des Termins, falls genannt - sonst 'Online' als sinnvoller Standardwert",
            },
            "organizer": {
                "type": "string",
                "description": "Organisator:in des Termins - 'Lumi', falls nicht anders genannt",
            },
            # Bugfix (siehe Bericht an die Nutzerin, gleicher Fund wie bei
            # PROPOSE_TICKET_TOOL): direkt an die Nutzer:in gerichtet, nicht
            # dritte Person.
            "reason": {
                "type": "string",
                "description": (
                    "Kurze Begründung, DIREKT an die Nutzer:in gerichtet (Anrede "
                    "'Du') - NICHT in dritter Person über sie ('Die Nutzer:in "
                    "hat...')."
                ),
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


_CODE_FENCE_RE = re.compile(r"```")
_BRACE_LINE_RE = re.compile(r"^\s*\{", re.MULTILINE)


def _strip_structured_tail(text: str) -> str:
    """Deterministischer Nachbearbeitungsschritt, KEIN dritter Prompt-Versuch
    (siehe Bericht an die Nutzerin): "genau ein Satz, kein JSON" im
    System-Prompt griff zweimal nicht zuverlässig - dasselbe Muster wie bei
    der Quellenangabe (info_agent_node) und den Sandbox-Grenzen
    (LUMI_CAPABILITIES): eine Modellanweisung ist keine Garantie. Schneidet
    stattdessen hart ab: alles ab dem ersten Markdown-Code-Zaun (```) ODER
    der ersten Zeile, die (nach führendem Whitespace) mit '{' beginnt, wird
    verworfen - je nachdem, was zuerst im Text vorkommt. Der Ankündigungssatz
    steht laut Beobachtung immer davor.

    Nur für die Knoten mit pending_action (infrastructure_agent_node/
    scheduling_agent_node) gedacht - info_agent_node ruft das NICHT auf,
    dort ist Markdown/Listen gewollt (siehe Bericht an die Nutzerin).

    Fallback auf den UNVERÄNDERTEN Text, falls nach dem Schnitt nichts
    Sichtbares übrig bliebe (z.B. eine Antwort, die NUR aus JSON bestünde,
    ohne Ankündigungssatz davor) - eine leere Nachricht wäre schlimmer als
    die alte, unbereinigte Anzeige."""
    cutoff = len(text)
    fence_match = _CODE_FENCE_RE.search(text)
    if fence_match:
        cutoff = min(cutoff, fence_match.start())
    brace_match = _BRACE_LINE_RE.search(text)
    if brace_match:
        cutoff = min(cutoff, brace_match.start())
    cleaned = text[:cutoff].rstrip()
    return cleaned if cleaned else text


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
        # Bugfix (siehe Bericht an die Nutzerin): dasselbe Prinzip wie oben,
        # jetzt für die Rationale-Herkunftsfelder. last_search_results wird
        # NUR von info_agent_node gesetzt, last_colleague NUR von
        # escalate_node, last_executed_action NUR von execute_action_node
        # (und dort auch nur, wenn tatsächlich etwas ausgeführt wurde) - läuft
        # DIESER Teilschritt über einen anderen Knoten (z.B. infrastructure_
        # agent), bleibt sonst der Wert eines VORHERIGEN Teilschritts stehen,
        # und rationale.py (build_rationale) leitet daraus einen Schritt ab,
        # der in DIESEM Teilschritt nie stattfand - inklusive einer
        # Quellenangabe für eine Suche, die nie lief. Der kritischere der
        # beiden Reset-Orte (siehe auch _base_state() in graph_runner.py):
        # genau der Fall "eine Nachricht zerfällt in zwei Teilschritte, nur
        # der erste sucht" lässt sich NICHT über einen reinen Per-Turn-Reset
        # abfangen, weil beide Teilschritte im selben Turn laufen.
        state["last_search_results"] = None
        state["last_colleague"] = None
        state["last_executed_action"] = None
        # Gleiches Prinzip, jetzt für die Ablehnen/Anpassen-Erkennung in
        # execute_action_node (siehe Bericht an die Nutzerin): last_decision/
        # last_declined_action werden NUR von human_review_node/
        # updated_query_node gesetzt - läuft dieser Teilschritt über einen
        # anderen Pfad (z.B. info_agent, kein pending_action, kein
        # interrupt), bliebe sonst die Entscheidung EINES VORHERIGEN
        # Teilschritts stehen und execute_action_node würde fälschlich eine
        # "kein Ticket"-Nachricht an einen Teilschritt hängen, der nie einen
        # Vorschlag hatte.
        state["last_decision"] = None
        state["last_declined_action"] = None
        # Gleiches Prinzip, jetzt für die Duplikat-Warnung (siehe Bericht an
        # die Nutzerin, Punkt 5): duplicate_notice wird NUR von
        # infrastructure_agent_node gesetzt - läuft dieser Teilschritt über
        # einen anderen Pfad, bliebe sonst die Warnung EINES VORHERIGEN
        # Teilschritts stehen und human_review_node würde fälschlich die
        # Warnkarte für einen Vorschlag zeigen, der gar kein Duplikat ist.
        # session_open_tickets NICHT zurückgesetzt - das ist eine
        # Turn-weite, bewusst konstante Momentaufnahme (siehe state.py),
        # kein Pro-Teilschritt-Wert.
        state["duplicate_notice"] = None
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
        # Erster system-Prompt an dieser Stelle überhaupt (siehe Bericht an
        # die Nutzerin) - der Supervisor kannte Lumis Fähigkeiten bisher gar
        # nicht, klassifizierte rein nach Thema (siehe DECOMPOSE_TOOL-Enum).
        system=(
            LUMI_CAPABILITIES
            + "\n\nNutze dieses Wissen über deine eigenen Fähigkeiten bei "
            "der Zuordnung: eine Bitte, tatsächlich etwas für die "
            "Nutzer:in zu TUN (nicht nur zu erklären), gehört zu der "
            "Kategorie, deren Aktion oben beschrieben ist - unabhängig "
            "vom Thema."
        ),
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

    # Gemeinsamer Fähigkeiten-Baustein statt eines lokalen "WICHTIG ZUR
    # EIGENEN ROLLE"-Blocks (siehe Bericht an die Nutzerin, LUMI_CAPABILITIES
    # oben) - der Entwurf hier und die strukturierte Ticket-Extraktion weiter
    # unten sind zwei bewusst UNABHÄNGIGE Modellaufrufe; ohne dieses Wissen
    # kann der Entwurf behaupten, den Zugang nicht selbst einrichten zu
    # können, während die Extraktion im selben Lauf genau dafür ein Ticket
    # anlegt.
    system_prompt += "\n\n" + LUMI_CAPABILITIES

    # Bugfix, zweite Runde (siehe Bericht an die Nutzerin): der vorige Fix
    # verhinderte den Widerspruch "das kann ich nicht", jetzt trat ein
    # milderer auf - der Entwurf stellt eine Rückfrage, während die separate
    # Extraktion (weiter unten) trotzdem schon ein fertiges Ticket
    # vorschlägt. Beide Hälften dieser Anweisung zusammen sorgen dafür, dass
    # der Entwurf entweder ganz klar VORSCHLÄGT oder ganz klar FRAGT, nie
    # beides gleichzeitig behauptet.
    #
    # Bugfix, dritte Runde (siehe Bericht an die Nutzerin): die Regel selbst
    # war richtig, ihre Beispiele ("welches Gerät, welche Berechtigung")
    # nicht - keines davon ist im Tool-Schema (PROPOSE_TICKET_TOOL) je
    # erforderlich, needed ist das einzige Pflichtfeld, subject/reason haben
    # Fallbacks. Das Modell generalisierte von diesen Beispielen trotzdem
    # auf praktisch jede Ticket-Anfrage und fragte fast immer zuerst nach -
    # jede Aktion wurde dadurch zweistufig, ohne dass die Rückfrage etwas
    # tatsächlich Blockierendes betraf. Ersetzt durch die Bedingung selbst
    # (ohne Info kein Tool-Aufruf möglich), ohne plausibel klingende, aber
    # tatsächlich unnötige Beispiele.
    system_prompt += (
        f"\n\nWICHTIG ZU RÜCKFRAGEN: Frag nur dann nach, wenn OHNE die "
        f"fehlende Information gar kein Ticket vorgeschlagen werden kann - "
        f"das ist bei einer IT-Anfrage praktisch nie der Fall: Betreff und "
        f"Begründung lassen sich immer sinnvoll aus der Anfrage ableiten, "
        f"auch ohne Detail wie Gerät oder Berechtigungsstufe - das kann im "
        f"Ticket offen bleiben, die IT klärt Details bei Bedarf direkt dort. "
        f"Im Regelfall schlägst du das Ticket also direkt vor, ohne "
        f"vorherige Rückfrage. Eine offene Rückfrage (nur im seltenen "
        f"echten Blockierfall) und die Beschreibung eines bereits "
        f"vorgeschlagenen/laufenden Tickets schließen sich gegenseitig aus - "
        f"schreib nie beides in dieselbe Antwort, und formuliere bei einer "
        f"Rückfrage NICHT so, als sei das Ticket schon unterwegs oder "
        f"abgeschlossen (kein \"das lege ich gleich an\"/\"das geht raus, "
        f"sobald...\"). Frag außerdem nie nach Dingen, die im Szenario "
        f"längst bekannt sind: du kennst die Nutzer:in (sie ist bereits "
        f"seit einigen Tagen im Onboarding) und die Kolleg:innen - Name "
        f"oder Startdatum musst du nicht erfragen."
    )

    # Bugfix (siehe Bericht an die Nutzerin): der Entwurf hier wird
    # geschrieben, BEVOR feststeht, dass eine Bestätigungskarte erscheint
    # (die separate Extraktion, die "needed" entscheidet, läuft erst
    # danach) - ohne diese Anweisung zählte das Modell Betreff/Beschreibung/
    # Priorität im Fließtext auf UND fragte am Ende erneut nach
    # Bestätigung, obwohl die Karte (falls sie kommt) genau das bereits
    # zeigt/abfragt. Gilt deshalb unbedingt, nicht nur "falls eine Karte
    # kommt" - Card-Existenz ist an dieser Stelle noch nicht bekannt.
    # Bugfix, zweite Runde (siehe Bericht an die Nutzerin): "keine
    # Aufzählung" reichte nicht - das Modell wich auf eine strukturierte
    # Darstellung aus (JSON-Block mit betreff/kontext/prioritaet direkt
    # nach dem Ankündigungssatz), die im Chat als abgeschnittener Code-Block
    # gerendert wurde - schlimmer als die ursprüngliche Aufzählung. "Keine
    # Aufzählung" allein schließt offenbar keine Formate aus, die keine
    # Liste im engeren Sinn sind - jetzt explizit: GENAU EIN Satz, keine
    # zweite Form daneben, in JEDER Gestalt (JSON, Code, Feld:Wert).
    system_prompt += (
        f"\n\nWICHTIG ZUR KÜRZE: Schlägst du (in der separaten Extraktion "
        f"weiter unten) ein Ticket vor, zeigt eine eigene Bestätigungskarte "
        f"danach automatisch Betreff, Kontext und Priorität an, mit eigenen "
        f"Knöpfen zum Bestätigen/Anpassen/Ablehnen. Deine GESAMTE Antwort "
        f"ist deshalb GENAU EIN Satz in normaler Alltagssprache, der "
        f"ankündigt, dass du ein Ticket anlegst (z.B. \"Klar, ich lege "
        f"dafür ein IT-Ticket an.\") - sonst NICHTS. Kein zweiter Absatz, "
        f"kein JSON, kein Code-Block, keine Feld:Wert-Paare, keine "
        f"Aufzählung, keine Liste, in KEINER Form - auch nicht zusätzlich "
        f"zum Satz. Frage am Ende NICHT erneut nach Bestätigung (\"Soll ich "
        f"das so anlegen?\" o.ä.) - das übernehmen die Knöpfe der Karte."
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
    # Bugfix, dritte Runde (siehe Bericht an die Nutzerin): der Prompt-Weg
    # ("genau ein Satz") griff zweimal nicht zuverlässig - deterministisch
    # im Code abgeschnitten statt ein drittes Mal am Prompt zu versuchen,
    # siehe _strip_structured_tail().
    state["draft_response"] = _strip_structured_tail(response.content[0].text)

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
            "aktuelle Anfrage vorgeschlagen werden soll. WICHTIG: Der Entwurf "
            "oben (letzte Assistant-Nachricht) ist Teil dieser Konversation - "
            "enthält er eine offene, noch unbeantwortete Rückfrage, OHNE deren "
            "Antwort gar kein Ticket vorgeschlagen werden kann, ist noch KEIN "
            "Ticket vorzuschlagen (needed=false). Das ist der SELTENE "
            "Ausnahmefall, nicht der Normalfall: fehlende Detailangaben wie "
            "Gerät oder Berechtigungsstufe verhindern kein Ticket (subject/"
            "reason/description lassen sich immer aus der Anfrage ableiten) "
            "- in diesem Fall bleibt needed=true."
        ),
        messages=extraction_messages,
        tools=[PROPOSE_TICKET_TOOL],
        tool_choice={"type": "tool", "name": "propose_ticket"},
    )
    action_data = _extract_tool_input(extraction_response, "propose_ticket")

    if action_data.get("needed"):
        state["pending_action"] = {
            "tool": "create_ticket",
            "args": {
                "department": "IT",
                "subject": action_data.get("subject", "IT-Anliegen"),
                # Pflichtfelder im Tool-Schema (siehe PROPOSE_TICKET_TOOL) -
                # .get()-Fallback hier trotzdem, falls das Modell sie je
                # ausließe, nicht als erwarteter Normalfall.
                "priority": action_data.get("priority", "normal"),
                # An die IT gerichtet, dritte Person - NICHT "reason" (siehe
                # PROPOSE_TICKET_TOOL für die Unterscheidung). Landet in
                # create_ticket() (tools.py) und damit im Ticket selbst.
                "description": action_data.get("description", ""),
            },
            "reason": action_data.get("reason", ""),
            "department": "IT",
            # Feste Policy statt Modelleinschätzung, siehe criticality_policy.py.
            "is_critical": is_tool_critical("create_ticket"),
        }
        # Duplikat-Erkennung (siehe Bericht an die Nutzerin, Punkt 5):
        # sandbox_state ist PRO THREAD, eine neue Anfrage sieht Tickets aus
        # anderen Anfragen derselben Sitzung sonst nie - state["session_open_
        # tickets"] wird deshalb von der API-Schicht (routes.py) VOR diesem
        # Turn session-weit befüllt (nur offene Tickets, siehe dort). Wort-
        # abgleich über text_matching.py - dieselbe Technik wie Suche/
        # Eskalation, kein neuer Mechanismus. Warntext exakt aus dem Design
        # übernommen (ConfirmationCard, node 229:5694), nicht neu erfunden.
        new_subject_words = tokenize(action_data.get("subject", ""))
        state["duplicate_notice"] = None
        if new_subject_words:
            for existing in state.get("session_open_tickets") or []:
                existing_words = tokenize(existing.get("subject", ""))
                if existing_words and any_word_matches(new_subject_words, existing_words):
                    state["duplicate_notice"] = (
                        f"Es gibt schon ein offenes Ticket mit dem Betreff "
                        f"{existing.get('subject', '')}"
                    )
                    break
    else:
        state["pending_action"] = None

    return state


# ---------------------------------------------------------------------------
# Info-Agent: allgemeine organisatorische Fragen, nutzt search_documents
# ---------------------------------------------------------------------------

# Zusätzlich zu text_matching.STOPWORDS (dort generisch für den Abgleich
# GEGEN Dokumente gedacht - "durchsuchen"/"knowledge"/"hub" sind dafür
# bewusst KEINE Stoppwörter, ein Satz wie "durchsuche den Hub nach
# Urlaubsregeln" soll ja weiterhin über "urlaubsregeln" treffen). Für die
# Frage "wurde überhaupt ein Thema genannt?" (siehe Bericht an die
# Nutzerin, Schritt 6) sind diese Wörter aber leer - sie beschreiben die
# Suchhandlung selbst oder ihr generisches Ziel, nicht das gesuchte
# Thema. Ohne diesen Zusatzfilter würde z.B. "Ich würde gern im
# Knowledge-Hub etwas nachschlagen." (newRequestSuggestions.ts) fälschlich
# als "hat ein Thema" durchgehen, weil keins dieser Wörter ein
# STOPWORDS-Eintrag im generischen Sinn ist - siehe text_matching.py.
_SEARCH_META_WORDS = {
    "durchsuchen", "durchsuche", "suchen", "suche", "nachschlagen",
    "nachschlage", "finden", "raussuchen", "knowledge", "hub",
    "wissensdatenbank", "wissenshub", "etwas", "irgendetwas", "mal",
    "thema", "stichwort", "gern", "wurde",
}

NO_SEARCH_TOPIC_RESPONSE = (
    "Ich kann den Knowledge-Hub gern durchsuchen, brauche aber noch ein "
    "Stichwort oder Thema, wonach ich suchen soll."
)


def _has_recognizable_search_topic(query: str) -> bool:
    """True, wenn nach text_matching.tokenize() UND Abzug der
    Suchhandlungs-Metawörter oben noch mindestens ein Wort übrig bleibt -
    siehe _SEARCH_META_WORDS-Kommentar. Deterministisch, kein Modellaufruf
    (dieselbe Begründung wie bei criticality_policy.py/suggestion_policy.py:
    der Fall ist eindeutig genug, um ihn nicht dem Modell zu überlassen)."""
    return bool(tokenize(query) - _SEARCH_META_WORDS)


def info_agent_node(state: OnboardingState) -> OnboardingState:
    query = state["current_task"]

    # Deterministische Themen-Erkennung VOR der Suche (siehe Bericht an die
    # Nutzerin, Schritt 6): fehlt ein erkennbares Thema, ist eine Suche
    # garantiert leer, unabhängig vom genauen Wortlaut - dieselbe Sorte
    # Rückfrage-vor-Handlung wie bei scheduling_agent_node (Wochentag/
    # Uhrzeit), hier aber deterministisch statt über einen freien
    # Modell-Entwurf gelöst (siehe _has_recognizable_search_topic-
    # Docstring). Betrifft nicht nur den Knowledge-Hub-Einstiegsvorschlag -
    # jede Nutzer:in-Formulierung ohne Suchbegriff (z.B. "kannst du mal was
    # nachschlagen?") nimmt denselben Zweig, das war der eigentliche Fund.
    if not _has_recognizable_search_topic(query):
        state["last_search_results"] = None
        state["draft_response"] = NO_SEARCH_TOPIC_RESPONSE
        state["pending_action"] = None
        return state

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

    # Gleiche Regel wie beim infrastructure_agent/scheduling_agent (siehe
    # Bericht an die Nutzerin) - hier nur die "kennt die Nutzer:in bereits"-
    # Hälfte, der Rückfrage-gegen-Vorschlag-Widerspruch kann hier nicht
    # auftreten, info_agent schlägt nie eine Aktion vor (pending_action
    # bleibt immer None, siehe unten).
    system_prompt += (
        f"\n\nFrag nie nach Dingen, die im Szenario längst bekannt sind: du "
        f"kennst die Nutzer:in (sie ist bereits seit einigen Tagen im "
        f"Onboarding) und die Kolleg:innen - Name oder Startdatum musst du "
        f"nicht erfragen."
    )

    # Gemeinsamer Fähigkeiten-Baustein (siehe Bericht an die Nutzerin,
    # LUMI_CAPABILITIES oben) - bewusst UNBEDINGT, nicht mehr nur im
    # if results:-Zweig: die frühere Fassung ließ info_agent nur dann wissen,
    # dass Lumi z.B. Tickets anlegen kann, wenn zufällig ein passender
    # Wissensartikel gefunden wurde. Genau das führte dazu, dass sie ihre
    # eigenen Fähigkeiten aus dem Artikeltext ableitete, statt sie zu
    # kennen ("gibt mir der verfügbare Inhalt keinen Hinweis darauf...").
    system_prompt += "\n\n" + LUMI_CAPABILITIES

    if results:
        # Bugfix (siehe Bericht an die Nutzerin): body statt summary - die
        # eine Satz-Zusammenfassung reichte für Detailfragen (z.B.
        # Resturlaub-Frist) strukturell nicht aus, nicht weil die Suche
        # versagte, sondern weil die Information nie im Kontext ankam.
        # summary bleibt für die Suchgewichtung selbst erhalten (siehe
        # knowledge_data.py), nur hier im Prompt-Kontext wird jetzt body
        # bevorzugt - INTRANET_POSTS haben kein body-Feld (Ankündigungen
        # sind bewusst kurz), fallen also auf summary zurück.
        docs_context = "\n\n".join(
            f"### {r['title']}\n{r.get('body') or r.get('summary', '')}" for r in results
        )
        system_prompt += (
            f"\n\nGefundene relevante Inhalte aus Knowledge Hub/Intranet:\n"
            f"{docs_context}\nNutze diese als Grundlage für deine Antwort, "
            f"erfinde keine Details, die dort nicht stehen. "
            f"VERBOTEN: eine Quellenangabe im Text zu nennen - in KEINER Form, "
            f"weder als \"(Quelle: ...)\" noch kursiv, noch als Fußnote, noch "
            f"als abschließender Satz. Deine Antwort endet mit dem letzten "
            f"inhaltlichen Satz, sonst nichts. Die Oberfläche zeigt Titel und "
            f"Fundstelle bereits zuverlässig in einem eigenen Block an - das "
            f"ist die einzige Quellenangabe, die die Nutzer:in sieht."
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

    # Gemeinsamer Fähigkeiten-Baustein statt eines lokalen "WICHTIG ZUR
    # EIGENEN ROLLE"-Blocks (siehe Bericht an die Nutzerin, LUMI_CAPABILITIES
    # oben) - der Entwurf hier und die strukturierte Termin-Extraktion weiter
    # unten sind zwei bewusst UNABHÄNGIGE Modellaufrufe; ohne dieses Wissen
    # kann der Entwurf behaupten, den Termin nicht selbst eintragen zu
    # können, während die Extraktion im selben Lauf genau das tut.
    system_prompt += "\n\n" + LUMI_CAPABILITIES

    # Bugfix, zweite Runde (siehe Bericht an die Nutzerin, gleiches Muster
    # wie beim infrastructure_agent): verhindert, dass der Entwurf eine
    # Rückfrage stellt, während die separate Extraktion (weiter unten)
    # trotzdem schon einen fertigen Termin vorschlägt.
    #
    # Bugfix, dritte Runde (siehe Bericht an die Nutzerin, gleiche Ursache
    # wie beim infrastructure_agent): "wer teilnimmt, welcher Raum" sind im
    # Tool-Schema (PROPOSE_CALENDAR_EVENT_TOOL) nicht erforderlich -
    # location/organizer haben Fallbacks ("Online"/"Lumi"). Der einzige
    # echte Blocker ist ein Termin, der sich ohne erkennbaren Wochentag oder
    # erkennbare Uhrzeit gar nicht ins Sandbox-Raster eintragen lässt.
    system_prompt += (
        f"\n\nWICHTIG ZU RÜCKFRAGEN: Frag nur dann nach, wenn OHNE die "
        f"fehlende Information gar kein Termin eingetragen werden kann - "
        f"das ist nur der Fall, wenn kein erkennbarer Wochentag oder keine "
        f"erkennbare Uhrzeit aus der Anfrage hervorgeht. Wer teilnimmt oder "
        f"welcher Raum gemeint ist, blockiert den Termin NICHT (Ort/"
        f"Organisator:in haben sinnvolle Standardwerte) - im Regelfall "
        f"schlägst du den Termin also direkt vor, ohne vorherige Rückfrage. "
        f"Eine offene Rückfrage (nur im seltenen echten Blockierfall) und "
        f"die Beschreibung eines bereits vorgeschlagenen/eingetragenen "
        f"Termins schließen sich gegenseitig aus - schreib nie beides in "
        f"dieselbe Antwort, und formuliere bei einer Rückfrage NICHT so, "
        f"als sei der Termin schon eingetragen oder unterwegs. Frag "
        f"außerdem nie nach Dingen, die im Szenario längst bekannt sind: du "
        f"kennst die Nutzer:in (sie ist bereits seit einigen Tagen im "
        f"Onboarding) und die Kolleg:innen - Name oder Startdatum musst du "
        f"nicht erfragen."
    )

    if state.get("pruefer_issues"):
        system_prompt += (
            "\n\nDeine letzte Antwort wurde beanstandet: "
            + "; ".join(state["pruefer_issues"])
            + ". Bitte korrigiere das in deiner nächsten Antwort."
        )

    # Kalender-Grenzen des Prototyps: müssen VOR dem Antwort-Entwurf bekannt
    # sein, nicht erst bei der strukturierten Extraktion danach - nur der
    # Entwurf erzeugt den natürlichsprachlichen Text, den die Nutzer:in
    # sieht (siehe Bericht an die Nutzerin: die Erklärung "nur diese Woche"
    # gehört in den Entwurf, nicht in die Extraktion, die nur noch
    # strukturiert erfasst, ob/wie ein Termin möglich ist).
    system_prompt += (
        f"\n\nWICHTIG ZUM KALENDER: {_sandbox_today_instruction()} Der Kalender "
        f"hier zeigt außerdem bewusst nur diese eine Woche (Montag bis Freitag). "
        f"Bezieht sich die Anfrage auf einen anderen Zeitraum (eine andere "
        f"Woche, 'nächsten Monat', 'in X Wochen') oder einen Samstag/Sonntag, "
        f"erkläre das der Nutzer:in kurz und freundlich als bewusste Grenze "
        f"dieses Prototyps - NICHT als Störung oder Fehler (z.B. so: \"Der "
        f"Kalender hier zeigt aktuell nur diese Woche - für [Zeitpunkt] kann "
        f"ich dir deshalb noch keinen Termin eintragen.\"). Biete stattdessen "
        f"an, einen Termin innerhalb dieser Woche einzutragen, falls das passt."
    )

    # Bugfix (siehe Bericht an die Nutzerin, gleiche Ursache wie beim
    # infrastructure_agent): der Entwurf wird geschrieben, BEVOR feststeht,
    # dass eine Bestätigungskarte erscheint - gilt deshalb unbedingt.
    #
    # Bugfix, zweite Runde (siehe Bericht an die Nutzerin, gleicher Fund wie
    # beim infrastructure_agent): "keine Aufzählung" schloss offenbar keine
    # strukturierte Darstellung aus, die keine Liste im engeren Sinn ist -
    # das Modell wich auf einen JSON-Block aus, der als abgeschnittener
    # Code-Block im Chat landete. Jetzt explizit: GENAU EIN Satz, keine
    # zweite Form daneben, in JEDER Gestalt.
    system_prompt += (
        f"\n\nWICHTIG ZUR KÜRZE: Schlägst du (in der separaten Extraktion "
        f"weiter unten) einen Termin vor, zeigt eine eigene Bestätigungskarte "
        f"danach automatisch Wochentag, Uhrzeit, Ort und Organisator:in an, "
        f"mit eigenen Knöpfen zum Bestätigen/Anpassen/Ablehnen. Deine "
        f"GESAMTE Antwort ist deshalb GENAU EIN Satz in normaler "
        f"Alltagssprache, der ankündigt, dass du den Termin einträgst - "
        f"sonst NICHTS. Kein zweiter Absatz, kein JSON, kein Code-Block, "
        f"keine Feld:Wert-Paare, keine Aufzählung, keine Liste, in KEINER "
        f"Form - auch nicht zusätzlich zum Satz. Frage am Ende NICHT erneut "
        f"nach Bestätigung (\"Soll ich das so eintragen?\" o.ä.) - das "
        f"übernehmen die Knöpfe der Karte."
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
    # Bugfix, dritte Runde (siehe Bericht an die Nutzerin, gleicher Fund wie
    # beim infrastructure_agent): deterministisch abgeschnitten statt ein
    # drittes Mal am Prompt zu versuchen, siehe _strip_structured_tail().
    state["draft_response"] = _strip_structured_tail(response.content[0].text)

    # 2. Strukturierte Aktions-Extraktion per Tool Use - analog
    # infrastructure_agent_node, nur mit dem Kalender-Tool-Schema. Braucht
    # dieselbe Datums-Referenz wie der Entwurf oben, sonst könnte die
    # Extraktion zu einer anderen within_current_week-Einschätzung kommen
    # als der bereits formulierte Entwurfstext.
    extraction_messages = call_messages + [
        {"role": "assistant", "content": state["draft_response"]},
        {"role": "user", "content": "Bewerte anhand des bisherigen Gesprächs: ist ein Kalendertermin nötig?"},
    ]
    extraction_response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        system=(
            "Entscheide anhand der Konversation, ob ein Kalendertermin für die "
            f"aktuelle Anfrage vorgeschlagen werden soll. {_sandbox_today_instruction()} "
            "WICHTIG: Der Entwurf oben (letzte Assistant-Nachricht) ist Teil "
            "dieser Konversation - enthält er eine offene, noch unbeantwortete "
            "Rückfrage, OHNE deren Antwort gar kein Termin eingetragen werden "
            "kann (kein erkennbarer Wochentag oder keine erkennbare Uhrzeit), "
            "ist noch KEIN Termin vorzuschlagen (needed=false). Das ist der "
            "SELTENE Ausnahmefall, nicht der Normalfall: fehlende Angaben wie "
            "Teilnehmer:innen oder Raum verhindern keinen Termin (location/"
            "organizer haben Fallbacks) - in diesem Fall bleibt needed=true."
        ),
        messages=extraction_messages,
        tools=[PROPOSE_CALENDAR_EVENT_TOOL],
        tool_choice={"type": "tool", "name": "propose_calendar_event"},
    )
    action_data = _extract_tool_input(extraction_response, "propose_calendar_event")

    if action_data.get("needed") and action_data.get("within_current_week"):
        state["pending_action"] = {
            "tool": "add_calendar_event",
            "args": {
                "weekday": action_data.get("weekday"),
                "hour": action_data.get("hour"),
                "title": action_data.get("title", "Termin"),
                "location": action_data.get("location", "Online"),
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
        # needed=True aber within_current_week=False landet hier ebenfalls:
        # kein Eintrag ohne verlässlichen weekday/hour, die Erklärung dazu
        # steht bereits im Entwurfstext oben (draft_response).
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


# Decision-Strings aus interrupt() sind Imperativ (Knopfbeschriftungen,
# siehe human_review_node/updated_query_node "options") - für den Verlauf
# (state["messages"]) braucht es die abgeschlossene Handlung, nicht die
# Aufforderung ("bestätigen" klingt als Nutzernachricht falsch, "Bestätigt"
# sagt, was passiert ist). EINE Quelle für beide Knoten (siehe Bericht an
# die Nutzerin), nicht in human_review_node UND updated_query_node kopiert.
# "anpassen" bleibt bewusst Infinitiv - das ist eine Aufforderung, keine
# abgeschlossene Handlung. WICHTIG: nur für die ANZEIGE im Verlauf - der
# Wert, der tatsächlich an POST /resume ging (die `decision`-Variable in
# beiden Knoten), bleibt unverändert und wird NIE überschrieben, sonst
# erkennt human_review_node die Zustimmung nicht mehr.
DECISION_PAST_TENSE = {
    "bestätigen": "Bestätigt",
    "ablehnen": "Abgelehnt",
    "anpassen": "Anpassen",
    "abbrechen": "Abgebrochen",
    "trotzdem bestätigen": "Trotzdem bestätigt",
}


def _decision_as_history_text(decision: str) -> str:
    return DECISION_PAST_TENSE.get(decision, decision)


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

    # change_notice: G13 ("Zustand hat sich geändert") bei updated_query,
    # Duplikat-Warnung (siehe Bericht an die Nutzerin, Punkt 5) bei
    # human_review - zwei unabhängige Quellen für dasselbe Feld, je nach
    # Zielknoten.
    if target_node == "updated_query":
        change_notice = state.get("change_description")
    elif target_node == "human_review":
        change_notice = state.get("duplicate_notice")
    else:
        change_notice = None

    log_interaction(
        category="interrupt_raised",
        node=target_node,
        session_id=state["session_id"],
        task=state.get("current_task"),
        channel=state["channel"],
        proposal=state.get("pending_action"),
        change_notice=change_notice,
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
    # Bugfix (siehe Bericht an die Nutzerin): der Klick auf einen
    # Bestätigungskarten-Knopf stand bisher NICHT im Verlauf, obwohl er
    # eine echte Entscheidung der Nutzer:in ist - für eine getippte Antwort
    # gilt das nicht. Läuft genau EINMAL: alles nach interrupt() wird bei
    # einem raisenden Aufruf nie erreicht (siehe announce_confirmation_node-
    # Docstring), nur der Resume-Durchlauf kommt hier vorbei.
    #
    # Bugfix, zweite Runde (siehe Bericht an die Nutzerin): im Verlauf soll
    # die abgeschlossene Handlung stehen, nicht die Knopfbeschriftung
    # (Imperativ) - siehe DECISION_PAST_TENSE. NUR für die Anzeige: `decision`
    # selbst bleibt unverändert, die Vergleiche unten (== "trotzdem
    # bestätigen") und log_interaction() nutzen weiterhin den Original-Wert.
    state["messages"].append({"role": "user", "content": _decision_as_history_text(decision)})
    state["last_decision"] = decision
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
        # last_declined_action VOR dem Zurücksetzen sichern - execute_action_node
        # (siehe dort) braucht Tool/Betreff für den Ablehn-/Anpass-Text, die sind
        # nach dieser Zeile sonst verloren.
        state["last_declined_action"] = state["pending_action"]
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
    # Duplikat-Warnung (siehe Bericht an die Nutzerin, Punkt 5): läuft über
    # dieselbe Warnkarten-Optik wie der G13-Fall (change_notice + 2-Knöpfe-
    # Set), kein neuer Frontend-Code. duplicate_notice wird von
    # infrastructure_agent_node gesetzt (siehe dort), bleibt sonst None -
    # dann unverändert das normale 3-Knöpfe-Set.
    duplicate_notice = state.get("duplicate_notice")
    options = ["trotzdem bestätigen", "abbrechen"] if duplicate_notice else ["bestätigen", "anpassen", "ablehnen"]
    decision = interrupt({
        "proposal": state["pending_action"],
        "change_notice": duplicate_notice,
        "options": options,
    })
    # Bugfix (siehe Bericht an die Nutzerin, gleiche Begründung wie in
    # updated_query_node): der Knopfdruck soll wie eine getippte Antwort im
    # Verlauf erscheinen - als abgeschlossene Handlung, nicht als
    # Knopfbeschriftung (siehe DECISION_PAST_TENSE). `decision` selbst
    # bleibt unverändert, siehe dortiger Kommentar.
    state["messages"].append({"role": "user", "content": _decision_as_history_text(decision)})
    state["last_decision"] = decision
    log_interaction(
        category="confirm", node="human_review",
        session_id=state["session_id"], task=state.get("current_task"),
        channel=state["channel"], decision=decision,
    )
    # Zustimmender Wert hängt vom gezeigten Knopf-Set ab (siehe oben) - bei
    # einer Duplikat-Warnung ist "trotzdem bestätigen" die Zustimmung, sonst
    # "bestätigen". Ein fester Vergleich auf "bestätigen" hätte im
    # Duplikat-Fall die Zustimmung fälschlich als Ablehnung behandelt.
    affirmative = "trotzdem bestätigen" if duplicate_notice else "bestätigen"
    if decision != affirmative:
        # last_declined_action VOR dem Zurücksetzen sichern - siehe Kommentar
        # in updated_query_node.
        state["last_declined_action"] = state["pending_action"]
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

    # Bugfix (siehe Bericht an die Nutzerin): escalate_node baut sein
    # instruction komplett separat aus ESCALATION_PROMPT auf, nutzt weder
    # build_system_prompt() noch LUMI_CAPABILITIES - war der einzige der
    # fünf Text-erzeugenden Knoten, der die Sandbox-Grenzen-Regel nie sah
    # (deshalb der Verweis auf "E-Mail, Telefon" bei einer Erreichbarkeits-
    # Eskalation). Voller Baustein, nicht nur der Grenzen-Teil - vermeidet
    # einen zweiten, separat zu pflegenden Auszug (siehe LUMI_CAPABILITIES-
    # Docstring: "eine Quelle, kein Duplikat woanders").
    instruction += "\n\n" + LUMI_CAPABILITIES

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
        weekday = args.get("weekday")
        hour = args.get("hour")
        # Nennt den TATSÄCHLICH eingetragenen (ggf. gerundeten) Zeitpunkt
        # explizit - siehe Bericht an die Nutzerin: eine Rundung (z.B.
        # "halb drei" -> 14 oder 15 Uhr) darf nicht stillschweigend
        # verschoben werden, die Person soll sehen, was wirklich passiert ist.
        time_phrase = None
        if isinstance(weekday, int) and 0 <= weekday < len(WEEKDAY_NAMES) and isinstance(hour, int):
            time_phrase = f"{WEEKDAY_NAMES[weekday]} um {hour:02d}:00 Uhr"
        if title and time_phrase:
            return f"Erledigt – „{title}“ ist am {time_phrase} im Kalender eingetragen."
        if title:
            return f"Erledigt – „{title}“ ist im Kalender eingetragen."
        return "Erledigt – der Termin ist eingetragen."

    if tool == "send_message":
        to = args.get("to")
        if to:
            return f"Erledigt – die Nachricht an {to} ist raus."
        return "Erledigt – die Nachricht ist gesendet."

    return "Erledigt."


def _decline_confirmation_text(action: dict) -> str:
    """Bewusst KEIN LLM-Aufruf, gleiches Prinzip wie
    _execution_confirmation_text() - reine, deterministische Bestätigung,
    dass NICHTS ausgeführt wurde (siehe Bericht an die Nutzerin: vorher
    blieb Lumi bei "ablehnen" stumm, weil execute_action_node ohne
    pending_action einfach gar nichts tat)."""
    tool = action.get("tool")
    if tool == "create_ticket":
        return "Alles klar, ich lege kein Ticket an."
    if tool == "add_calendar_event":
        return "Alles klar, ich trage den Termin nicht ein."
    return "Alles klar, das mache ich nicht."


def _adjust_prompt_text(action: dict) -> str:
    """Bewusst KEIN LLM-Aufruf - reine Rückfrage. Das eigentliche Anpassen
    passiert im NÄCHSTEN Turn per normaler Nutzer-Nachricht: die volle
    Konversation inkl. dieser Rückfrage steht dem jeweiligen Sub-Agenten
    dann wieder zur Verfügung (state["messages"], siehe infrastructure_
    agent_node/scheduling_agent_node) - kein eigener "Bearbeiten"-
    Mechanismus nötig, das ergibt sich aus dem normalen Gesprächsverlauf."""
    tool = action.get("tool")
    args = action.get("args") or {}
    subject = args.get("subject") or args.get("title")
    if tool == "create_ticket":
        if subject:
            return f"Klar, was möchtest du an „{subject}“ ändern?"
        return "Klar, was möchtest du am Ticket ändern?"
    if tool == "add_calendar_event":
        if subject:
            return f"Klar, was möchtest du an „{subject}“ ändern?"
        return "Klar, was möchtest du am Termin ändern?"
    return "Klar, was möchtest du ändern?"


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
    else:
        # Bugfix (siehe Bericht an die Nutzerin): "ablehnen"/"anpassen"
        # (bzw. "abbrechen" im G13-Fall) liefen bisher hier komplett still
        # durch - state["last_decision"]/state["last_declined_action"]
        # (gesetzt in human_review_node/updated_query_node, siehe dort)
        # unterscheiden das jetzt von "es gab nie einen Vorschlag" (z.B.
        # info_agent-Pfad, wo beide Felder None bleiben - siehe Reset in
        # supervisor_node/_base_state()).
        decision = state.get("last_decision")
        declined_action = state.get("last_declined_action")
        if declined_action and decision in ("ablehnen", "abbrechen"):
            state["messages"].append(
                {"role": "assistant", "content": _decline_confirmation_text(declined_action)}
            )
        elif declined_action and decision == "anpassen":
            state["messages"].append(
                {"role": "assistant", "content": _adjust_prompt_text(declined_action)}
            )
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
