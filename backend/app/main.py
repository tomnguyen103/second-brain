from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from app.api import (
    briefing,
    capture,
    chat,
    conversations,
    dataops,
    health,
    ingest,
    research_jobs,
    search,
    sources,
    tasks,
)
from app.config import settings
from app.obs.metrics import PrometheusMiddleware, render

app = FastAPI(title="Second Brain API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Second-Brain-Admin-Token"],
    allow_credentials=False,
)
if settings.metrics_enabled:
    app.add_middleware(PrometheusMiddleware)

    @app.get("/metrics", include_in_schema=False)
    def metrics_endpoint() -> Response:
        """Prometheus exposition endpoint (scraped by the Prometheus service)."""
        body, content_type = render()
        return Response(content=body, media_type=content_type)

app.include_router(health.router)
app.include_router(capture.router)
app.include_router(ingest.router)
app.include_router(chat.router)
app.include_router(search.router)
app.include_router(conversations.router)
app.include_router(dataops.router)
app.include_router(briefing.router)
app.include_router(tasks.router)
app.include_router(research_jobs.router)
app.include_router(sources.router)
