"""
Vorbelegte Anfragen für neue Sessions (siehe Auftrag "VORBELEGTE ANFRAGEN").

Platzhaltertexte - die Nutzerin liefert die echten Inhalte separat nach.
NICHT als tatsächliche Studieninhalte verwenden.
"""

# 2-3 Templates, siehe Auftrag. Jedes Template ist eine vollständige,
# bereits "freigegebene" Mini-Historie im Format, das graph.py erwartet
# (siehe state.py: messages: list[{"role": ..., "content": ...}]).
PRESEED_TEMPLATES: list[list[dict]] = [
    [
        {
            "role": "user",
            "content": "[PLATZHALTER] Erste vorbelegte Anfrage – Thema A. Hier kommt später ein echter Gesprächseinstieg hin.",
        },
        {
            "role": "assistant",
            "content": "[PLATZHALTER] Beispielhafte Lumi-Antwort zu Thema A – wird später durch echten Inhalt ersetzt.",
        },
    ],
    [
        {
            "role": "user",
            "content": "[PLATZHALTER] Zweite vorbelegte Anfrage – Thema B. Hier kommt später ein echter Gesprächseinstieg hin.",
        },
        {
            "role": "assistant",
            "content": "[PLATZHALTER] Beispielhafte Lumi-Antwort zu Thema B – wird später durch echten Inhalt ersetzt.",
        },
    ],
]
