"""
Strukturierte Kolleg:innen-Daten (aus Fiktive_Firma_und_Kollegen.md), damit
der Agent bei einem Verweis echte Personen/Zuständigkeiten nennt, statt sie
zu erfinden (siehe ADR-004, G7/G8 aus dem Guideline-Set).
"""

COLLEAGUES = [
    {
        "name": "Max Vogel",
        "department": "IT",
        "role": "IT Support",
        "topics": ["vpn", "zugang", "hardware", "software", "laptop", "passwort"],
    },
    {
        "name": "Anna Schmidt",
        "department": "HR",
        "role": "HR Business Partnerin",
        "topics": ["urlaub", "vertrag", "gehalt", "krankmeldung", "sonderurlaub", "onboarding"],
    },
    {
        "name": "Tom Bauer",
        "department": "Vertrieb",
        "role": "Vertrieb, Buddy",
        "topics": ["kaffee", "kennenlernen", "team", "kalender", "meeting"],
    },
    {
        "name": "Laura Seifert",
        "department": "Controlling",
        "role": "Controlling",
        "topics": ["budget", "kosten", "reisekosten"],
    },
    {
        "name": "Lars Becker",
        "department": "Marketing",
        "role": "Marketing",
        "topics": ["marketing", "kampagne", "webseite"],
    },
]


def find_colleague_for_topic(topic: str) -> dict | None:
    """Findet die zuständige Person zu einem Thema über einfaches Keyword-Matching."""
    topic_lower = topic.lower()
    for colleague in COLLEAGUES:
        if any(t in topic_lower for t in colleague["topics"]):
            return colleague
    return None
