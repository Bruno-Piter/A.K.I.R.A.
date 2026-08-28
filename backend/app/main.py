from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import chat, documents, graph, health
from app.core.settings import settings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        from app.arms.routines.checkpoint import get_checkpointer

        get_checkpointer()
    except Exception:
        pass
    try:
        from app.arms.memory import ensure_schema, get_driver

        ensure_schema(get_driver())
    except Exception:
        pass
    try:
        from app.arms.routines.ingest_graph import get_ingest_graph
        from app.arms.routines.query_graph import get_query_graph

        _app.state.query_graph = get_query_graph()
        _app.state.ingest_graph = get_ingest_graph()
    except Exception:
        _app.state.query_graph = None
        _app.state.ingest_graph = None
    try:
        yield
    finally:
        try:
            from app.arms.routines.checkpoint import close_checkpointer

            close_checkpointer()
        except Exception:
            pass
        try:
            from app.arms.memory import close_driver

            close_driver()
        except Exception:
            pass


app = FastAPI(
    title=settings.app_name,
    description="Agentic Knowledge Integration & Retrieval Architecture",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(documents.router, prefix="/api", tags=["documents"])
app.include_router(graph.router, prefix="/api", tags=["graph"])


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "health": "/api/health",
    }