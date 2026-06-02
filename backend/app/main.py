from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from app.api import chat, conversations, dataops, health, ingest, search
from app.config import settings
from app.obs.metrics import PrometheusMiddleware, render

app = FastAPI(title="Second Brain API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)
if settings.metrics_enabled:
    app.add_middleware(PrometheusMiddleware)

    @app.get("/metrics", include_in_schema=False)
    def metrics_endpoint() -> Response:
        body, content_type = render()
        return Response(content=body, media_type=content_type)

app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(chat.router)
app.include_router(search.router)
app.include_router(conversations.router)
app.include_router(dataops.router)
