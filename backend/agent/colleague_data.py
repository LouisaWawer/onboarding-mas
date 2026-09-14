"""
Strukturierte Kolleg:innen-Daten (aus Fiktive_Firma_und_Kollegen.md), damit
der Agent bei einem Verweis echte Personen/Zuständigkeiten nennt, statt sie
zu erfinden (siehe ADR-004, G7/G8 aus dem Guideline-Set).
"""

from .text_matching import tokenize, any_word_matches

COLLEAGUES = [
    {
        "name": "Max Vogel",
        "department": "IT",
        "role": "IT Support",
        "topics": [
            "vpn", "zugang", "hardware", "software", "laptop", "passwort",
            "berechtigung", "profil", "account", "rechte", "freigabe",
        ],
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
    """Findet die zuständige Person zu einem Thema über Wort- statt
    Teilstring-Vergleich (siehe Bericht an die Nutzerin: reiner
    Teilstring-Vergleich scheiterte an deutscher Flexion, z.B. "zugang" in
    "unbeschränkten Zugängen" - "ä" != "a" als Zeichen, selbst nach
    .lower()). tokenize()/any_word_matches() aus text_matching.py bringen
    Wortgrenzen, Umlaut-Normalisierung und den gleichen Präfix-Fallback wie
    die Wissensdatenbank-Suche - dieselbe Technik, eine Quelle."""
    topic_words = tokenize(topic)
    if not topic_words:
        return None
    for colleague in COLLEAGUES:
        colleague_words = tokenize(" ".join(colleague["topics"]), filter_stopwords=False)
        if any_word_matches(topic_words, colleague_words):
            return colleague
    return None
