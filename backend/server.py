# WICHTIG: load_dotenv() muss laufen, BEVOR api.config (liest STUDY_ACCESS_CODE
# etc. beim Modul-Import) oder agent.graph importiert wird - siehe
# Setup_Dokumentation.md Abschnitt 2 ("bekannte Stolperfallen").
from dotenv import load_dotenv

load_dotenv()

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.sqlite import SqliteSaver

from agent.graph import build_graph
from api.config import CHECKPOINTS_DB_PATH, SANDBOX_DIST_DIR, APP_DB_PATH
from api.events import SessionEventBus
from api.routes import router as api_router
from api.store import Store


@asynccontextmanager
async def lifespan(app: FastAPI):
    # SqliteSaver.from_conn_string() ist ein Context-Manager, kein direktes
    # Objekt (siehe Setup_Dokumentation.md Abschnitt 2) - für einen
    # langlebigen Server wird der `with`-Block hier über den FastAPI-
    # Lifespan aufgespannt, statt (wie in test_graph.py) pro Testlauf.
    with SqliteSaver.from_conn_string(CHECKPOINTS_DB_PATH) as checkpointer:
        app.state.graph = build_graph(checkpointer)
        app.state.store = Store(APP_DB_PATH)
        app.state.event_bus = SessionEventBus(asyncio.get_running_loop())
        # Threads mit einem gerade aktiven Hintergrund-Lauf (verhindert
        # doppelte Läufe auf derselben Anfrage, siehe routes.py) bzw.
        # laufende asyncio-Tasks (Referenz halten, sonst droht vorzeitige
        # Garbage Collection fire-and-forget-artiger Tasks).
        app.state.active_threads = set()
        app.state.background_tasks = set()
        try:
            yield
        finally:
            app.state.store.close()


app = FastAPI(lifespan=lifespan)

# Für den lokalen Entwicklungsbetrieb (sandbox-app läuft über den
# Vite-Devserver auf einem anderen Port, siehe Auftrag Punkt 9). Im
# gehosteten Betrieb (gleiche Origin) wirkungslos, aber harmlos.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/ping")
def ping():
    return {"status": "ok"}


app.include_router(api_router)


# ---------------------------------------------------------------------------
# 9. Static-Serving des Frontends (siehe Auftrag Punkt 9)
# ---------------------------------------------------------------------------
# Bewusst NACH den API-Routen registriert (Starlette prüft in
# Registrierungsreihenfolge) und nur, wenn sandbox-app/dist tatsächlich
# existiert - im Entwicklungsbetrieb (Vite-Devserver, dist/ ungebaut) wird
# dieser Block komplett übersprungen und stört damit nichts.
if SANDBOX_DIST_DIR.is_dir():
    assets_dir = SANDBOX_DIST_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Catch-all auf index.html, damit clientseitiges Routing nicht in
        # 404 läuft - API-Routen wurden oben bereits registriert und
        # "gewinnen" daher vor diesem Catch-all.
        candidate = SANDBOX_DIST_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(SANDBOX_DIST_DIR / "index.html")
