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

Struktur (siehe Bericht an die Nutzerin, Schritt 6, Design-Korrektur):
Karte statt Einzelzeile - eine Instanz derselben Figma-Variante wie die
ConfirmationCard ("type=options", node 219:4794), NICHT die
Aufgabenauswahl-Verwendung dieser Variante (die bleibt Backlog, siehe
OptionsCard.tsx). `title` ersetzt das frühere einzelne `displayed`,
`options` ersetzt das frühere einzelne `submitted` - JEDE Option trägt
BEIDES einzeln: `displayed` das kurze Options-Label (Button-Text, z.B.
"Neue Besprechung planen"), `submitted` der tatsächliche, natürlich
formulierte Nutzernachrichten-Text nach einem Klick (z.B. "Ich möchte
eine neue Besprechung planen."). Bugfix ggü. der vorherigen Fassung:
`submitted` wurde dort nie tatsächlich übertragen (weder im
status_changed-Event noch in resolve_pending_suggestion() unten) - nur
`displayed` verließ je das Backend, `submitted` war totes Feld. Jetzt
zwingend nötig, weil ein kurzes Options-Label (anders als der frühere
volle Angebots-Satz) nicht mehr selbst als Nutzernachricht taugt.

tickets/hub/intranet bewusst NICHT enthalten - Texte liefert die
Nutzerin nach, sobald die Struktur steht. Kein Platzhalter aus den
alten Einzelzeilen-Texten (falsche Form: Aussagesatz statt Frage-Titel
+ Optionsliste) - der bestehende "kein Eintrag in SUGGESTION_POLICY"-
No-Op in routes.py (post_screen) deckt das bereits ab, kein Code nötig.
"""

from typing import TypedDict


class SuggestionOption(TypedDict):
    displayed: str
    submitted: str


class SuggestionCard(TypedDict):
    title: str
    options: list[SuggestionOption]


SUGGESTION_POLICY: dict[str, SuggestionCard] = {
    "calendar": {
        "title": "Ich sehe du bist im Kalender. Wie kann ich dich unterstützen?",
        "options": [
            {
                "displayed": "Neue Besprechung planen",
                "submitted": "Ich möchte eine neue Besprechung planen.",
            },
            {
                "displayed": "Besprechung absagen",
                "submitted": "Ich möchte eine Besprechung absagen.",
            },
            {
                "displayed": "Besprechung verschieben",
                "submitted": "Ich möchte eine Besprechung verschieben.",
            },
        ],
    },
}
