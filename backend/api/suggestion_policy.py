"""
Vorschlags-Policy pro Sandbox-Screen - feste Zuordnung, KEIN Modellaufruf.

Setzt "proaktive Vorschläge beim Screenwechsel" um (Guideline 21,
kalibrierte Einstiegsphase). Ein Graph-Durchlauf bei jedem Screenwechsel
würde 10-50s dauern und jede Testperson etwas anderes sehen lassen -
dieselbe Begründung wie bei agent/criticality_policy.py: der AUSLÖSER
ist eine feste Regel, NUR die Antwort NACH einem Klick kommt vom
echten Agenten (der Klick wird als ganz normale Nutzernachricht in den
Graphen gegeben, siehe routes.py: post_message).

Bewusst in api/, nicht in agent/ (anders als criticality_policy.py):
graph.py sieht diese Tabelle nie - sie wird ausschließlich von
routes.py/graph_runner.py gelesen, BEVOR überhaupt eine Anfrage/ein
Graph-Lauf existiert. Lokalität schlägt Paarigkeit mit
criticality_policy.py (siehe Bericht an die Nutzerin).

Screen-IDs entsprechen SidebarApp aus dem Frontend (siehe
sandbox-app/src/components/Sidebar/Sidebar.tsx, CODE_UEBERSICHT.md):
intranet | chat | hub | tickets | calendar - 'calendar', NICHT
'kalender' (deutscher Screen-Name, aber englische interne ID, siehe
CODE_UEBERSICHT.md). 'chat' bewusst NICHT enthalten - dort Hilfe
anzubieten ergibt keinen Sinn, man ist ohnehin bei Lumi.
"""

SUGGESTION_POLICY: dict[str, dict[str, str]] = {
    "calendar": {
        "displayed": "Wenn du einen Termin eintragen willst, mache ich das gern für dich.",
        "submitted": "Ich möchte einen Termin eintragen.",
    },
    "tickets": {
        "displayed": "Wenn du etwas von einem Team brauchst, kann ich daraus ein Ticket machen.",
        "submitted": "Ich brauche etwas von einem Team und möchte eine Anfrage stellen.",
    },
    "hub": {
        "displayed": "Wenn du nicht findest wonach du suchst, frag mich direkt.",
        "submitted": "Ich suche etwas in der Wissensdatenbank und finde es nicht.",
    },
    "intranet": {
        "displayed": "Falls du wissen willst, wer hier wofür zuständig ist: frag mich.",
        "submitted": "Wer ist bei Nordlicht wofür zuständig?",
    },
}
