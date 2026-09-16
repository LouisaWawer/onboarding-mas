"""
Exportiert den kompilierten LangGraph-Graphen (build_graph() in
agent/graph.py) als PNG + rohen Mermaid-Text - für eine code-akkurate
Graph-Abbildung in der Bachelorarbeit, nicht von Hand nachgezeichnet.

Rein lesend gegenüber graph.py: importiert nur build_graph(), verändert
dort nichts. Eigenständig lauffähig, kein Server/keine laufende Anfrage
nötig - der Graph wird nur KOMPILIERT (graph.compile()), nie ausgeführt
(kein .invoke()/.stream()/.get_state()).

CHECKPOINTER-WAHL (siehe Bericht an die Nutzerin): checkpointer=None.
build_graph() reicht den Parameter unverändert an graph.compile() durch;
LangGraph prüft beim COMPILE nicht, ob ein interrupt()-Knoten einen
Checkpointer hat - das wird erst beim tatsächlichen invoke()/stream()
relevant (siehe SqliteSaver-Verwendung in server.py/test_graph.py). Da
dieses Skript ausschließlich compiled.get_graph() abfragt (die reine
Struktur-Repräsentation für die Zeichnung), wird der Checkpointer nie
benutzt - kein In-Memory-Checkpointer nötig, keine zusätzliche Abhängigkeit
für ein reines Export-Skript.

VORAUSSETZUNG: aus backend/ heraus ausführen (wie test_graph.py), damit
graph.py's eigener load_dotenv()-Aufruf backend/.env findet -
ANTHROPIC_API_KEY wird nur für die Client-Konstruktion in graph.py
gebraucht (Modul-Import), hier nie tatsächlich für einen API-Aufruf
verwendet.

draw_mermaid_png() rendert standardmäßig über den externen Dienst
mermaid.ink (Netzwerkzugriff nötig) - schlägt das fehl (kein Internet,
Dienst nicht erreichbar), bricht das Skript NICHT komplett ab: der
Mermaid-Rohtext (graph.mmd) ist zu dem Zeitpunkt bereits geschrieben und
lässt sich bei Bedarf über einen beliebigen anderen Mermaid-Renderer
(mermaid.live, VS-Code-Extension, mermaid-cli) von Hand in ein PNG
umwandeln.

Ausführen:
    cd backend && python3.12 export_graph_diagram.py
"""

from pathlib import Path

from agent.graph import build_graph

OUTPUT_DIR = Path(__file__).parent / "docs" / "graph_export"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # checkpointer=None: siehe Moduldocstring - der Graph wird hier nur
    # kompiliert und inspiziert, nie ausgeführt.
    compiled = build_graph(checkpointer=None)
    graph_repr = compiled.get_graph()

    mermaid_text = graph_repr.draw_mermaid()
    mermaid_path = OUTPUT_DIR / "graph.mmd"
    mermaid_path.write_text(mermaid_text, encoding="utf-8")
    print(f"[ok] Mermaid-Text geschrieben: {mermaid_path}")

    png_path = OUTPUT_DIR / "graph.png"
    try:
        png_bytes = graph_repr.draw_mermaid_png()
        png_path.write_bytes(png_bytes)
        print(f"[ok] PNG geschrieben: {png_path}")
    except Exception as exc:  # noqa: BLE001 - bewusst breit, siehe Moduldocstring
        print(
            f"[fehler] PNG-Export fehlgeschlagen ({exc!r}) - vermutlich kein "
            f"Netzwerkzugriff auf mermaid.ink. {mermaid_path} steht trotzdem "
            f"zur Verfügung, z.B. für mermaid.live oder mermaid-cli."
        )

    # Punkt 4 des Auftrags: Knoten-/Kanten-Liste zum Abgleich gegen die
    # eigene Dokumentation - direkt aus derselben graph_repr, die auch das
    # Diagramm erzeugt hat, nicht separat von Hand aus graph.py abgetippt.
    print("\n--- Knoten ---")
    for node_id in sorted(graph_repr.nodes):
        print(f"  {node_id}")

    print("\n--- Kanten ---")
    for edge in graph_repr.edges:
        label = f"  label={edge.data!r}" if edge.data else ""
        cond = " (conditional)" if edge.conditional else ""
        print(f"  {edge.source} -> {edge.target}{cond}{label}")


if __name__ == "__main__":
    main()
