"""
Strukturierte Inhalte aus Knowledge_Hub_Inhalte.md und Intranet_Inhalte.md.

Diese Datei hält die Artikel/Beiträge als durchsuchbare Datenstruktur bereit,
damit der Agent echte Inhalte findet statt sie zu erfinden. Bei neuen
Artikeln: hier ergänzen (Inhalt bleibt mit den .md-Dateien synchron halten).
"""

KNOWLEDGE_ARTICLES = [
    {
        "id": "urlaub-beantragen",
        "title": "Urlaub beantragen",
        "path": "HR / Abwesenheit / Urlaub",
        "category": "HR",
        "summary": "Wie du Urlaub über die Tickets-App beantragst, Fristen, Genehmigung, Resturlaub.",
    },
    # Weitere Artikel hier ergänzen, z.B.:
    # {"id": "vpn-zugang", "title": "VPN-Zugang einrichten", "path": "IT", ...},
]

INTRANET_POSTS = [
    {
        "title": "Save the Date: Sommerfest am 15. September",
        "author": "Anna Schmidt",
        "category": "Ankündigung",
        "summary": "Firmenfest mit Live-Musik und Grill auf der Dachterrasse.",
    },
    {
        "title": "IT-Wartungsfenster am kommenden Wochenende",
        "author": "Max Vogel",
        "category": "Ankündigung",
        "summary": "Geplante Wartung, VPN/Tools ggf. eingeschränkt erreichbar.",
    },
    {
        "title": "Neue Kaffeemaschine im 3. Stock",
        "author": "Tom Bauer",
        "category": "Ankündigung",
        "summary": "Neue Maschine inkl. Hafermilch-Option verfügbar.",
    },
]


def search_knowledge_and_intranet(query: str, top_k: int = 3) -> list[dict]:
    """Einfache Keyword-Suche über Titel + Zusammenfassung.

    Wortweiser, BEIDSEITIGER Teilstring-Vergleich (statt nur "Anfragewort
    exakt im Gesamttext enthalten") - das fängt Wortformen wie
    "Urlaubsregelung" vs. Artikel-Titel "Urlaub" ab, die sich sonst nicht
    treffen, obwohl sie inhaltlich zusammengehören. Bewusst simpel (keine
    Embeddings/Vektorsuche) - für die überschaubare Anzahl Artikel im
    Prototyp ausreichend. Bei Bedarf später durch semantische Suche
    ersetzbar, ohne die Tool-Schnittstelle zu ändern.
    """
    query_words = query.lower().split()
    all_content = [{**a, "source": "knowledge_hub"} for a in KNOWLEDGE_ARTICLES] + [
        {**p, "source": "intranet"} for p in INTRANET_POSTS
    ]

    scored = []
    for item in all_content:
        text_words = f"{item['title']} {item.get('summary', '')}".lower().split()
        score = 0
        for qw in query_words:
            if any(qw in tw or tw in qw for tw in text_words):
                score += 1
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:top_k]]
