"""Content hashing for dedupe (documents.content_hash, UNIQUE(source_id, content_hash))."""
from __future__ import annotations

import hashlib
import re

_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    return _WS.sub(" ", text or "").strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()
