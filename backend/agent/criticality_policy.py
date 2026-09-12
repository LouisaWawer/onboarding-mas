"""
Kritikalitäts-Policy pro Tool - feste Zuordnung, KEINE Modelleinschätzung.

Setzt die "Firmenrichtlinie als Untergrenze" um (siehe Kapitel 4.4 der
Arbeit / ADR-004 Guardrail-Strategie in Projekt_Vorlagen_Prototyp.md).

Vorher wurde is_critical vom Modell selbst pro Anfrage geschätzt (Teil der
propose_ticket-/propose_calendar_event-Tool-Schemas in graph.py) - dieselbe
Anfrage konnte über mehrere Läufe unterschiedliche Werte bekommen (z.B.
dieselbe VPN-Anfrage: mal true, mal false). Für eine Studie, in der
verschiedene Testpersonen bei identischer Aufgabe dasselbe Systemverhalten
erleben sollen, ist das nicht tragbar - deshalb jetzt eine feste, von der
Anfrage unabhängige Zuordnung. Bewusst NICHT in prompts_config.py: das ist
keine Prompt-Formulierung, die nach Interviewauswertung verfeinert wird,
sondern eine Policy-Entscheidung, die unverändert bleibt, unabhängig davon,
was das Modell sagen würde - der Code soll das nicht so aussehen lassen,
als würde hier eine Einschätzung stattfinden, die dann verworfen wird.
"""

TOOL_CRITICALITY: dict[str, bool] = {
    "create_ticket": True,
    "send_message": True,
    "add_calendar_event": False,
}


def is_tool_critical(tool_name: str) -> bool:
    """Default True für nicht gelistete Tools - im Zweifel bestätigen
    lassen, statt ein unbekanntes Tool stillschweigend als unkritisch zu
    behandeln."""
    return TOOL_CRITICALITY.get(tool_name, True)
