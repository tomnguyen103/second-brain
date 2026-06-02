from functools import lru_cache
from app.config import settings as _settings
from app.db.session import get_db                     # re-exported for routers
from app.embeddings.encoder import Embedder
from app.llm.factory import get_llm_client


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    return Embedder()


def get_settings():
    return _settings


__all__ = ["get_db", "get_embedder", "get_settings", "get_llm_client"]
