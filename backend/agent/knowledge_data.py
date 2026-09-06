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

    Bewusst simpel (keine Embeddings/Vektorsuche) - für die überschaubare
    Anzahl Artikel im Prototyp ausreichend. Bei Bedarf später durch
    semantische Suche ersetzbar, ohne die Tool-Schnittstelle zu ändern.
    """
    query_lower = query.lower()
    all_content = [{**a, "source": "knowledge_hub"} for a in KNOWLEDGE_ARTICLES] + [
        {**p, "source": "intranet"} for p in INTRANET_POSTS
    ]

    scored = []
    for item in all_content:
        text = f"{item['title']} {item.get('summary', '')}".lower()
        score = sum(1 for word in query_lower.split() if word in text)
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:top_k]]
