# Phase 1 — RAG MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking. Work TDD: red → green → commit. DRY. YAGNI.

**Goal:** Ship `POST /ingest` and `POST /chat` on the Phase 0 schema — local embeddings on
ingest, hybrid (pgvector + full-text) retrieval fused with RRF, and cited answers from an
`LLMClient` (Gemini default / Ollama / fake), with conversations, messages, and retrievals
persisted.

**Architecture:** FastAPI + synchronous SQLAlchemy 2.0 (psycopg3). Ingest is inline
(chunk → embed → store). Chat is non-streaming (retrieve → fuse → prompt → generate → persist).
All model calls go through one `LLMClient` seam; embeddings are local `all-MiniLM-L6-v2`
(384-d), used at ingest **and** to embed the query at chat time. See ADR-0005 (retrieval/RRF),
ADR-0006 (prompt/citations), ADR-0007 (API + execution model).

**Tech stack:** Python 3.12, FastAPI, Uvicorn, SQLAlchemy 2.0 + psycopg3, pgvector,
sentence-transformers (torch), google-genai (Gemini), httpx (Ollama), pytest. Postgres 16 +
pgvector via the existing `docker-compose.yml` (`pgvector/pgvector:pg16`).

---

## Prerequisites & environment

- **Backend venv on Python 3.12** (torch has no reliable cp314 wheel yet — see
  `implementation-notes.md`). The machine already has CPython 3.12.13 via the `py` launcher.
  ```powershell
  cd backend
  py -V:Astral/CPython3.12.13 -m venv .venv    # or: py -3.12 -m venv .venv
  .\.venv\Scripts\Activate.ps1
  python -m pip install -U pip
  pip install -r requirements.txt
  copy .env.example .env
  ```
- **Docker Desktop** is required only for the DB-bound tasks (8–12) and the end-to-end smoke.
  Tasks 1–7 (everything DB-free) run today without it.
- **Gemini key** (`SECOND_BRAIN_GEMINI_API_KEY`) is needed only for real Gemini answers. Tests
  and offline smoke use `SECOND_BRAIN_LLM_PROVIDER=fake` — no key, no network.

**DB-free tasks** (no Docker): 1, 3, 4, 5*, 6, 7. **DB-bound tasks** (need Docker): 2, 8, 9,
10, 11, 12. (*Task 5's real-model test is marked `slow`; its interface test is DB-free and
network-free via monkeypatch.)

---

## File structure (created/modified in this phase)

```
backend/
  requirements.txt                 # MODIFY: add fastapi, uvicorn, sentence-transformers,
                                    #         google-genai, httpx, pytest
  app/
    config.py                      # MODIFY: LLM/embedding/retrieval/CORS settings
    main.py                        # CREATE: FastAPI app, CORS, routers, dependencies
    deps.py                        # CREATE: get_db / get_embedder / get_settings / get_llm
    db/
      session.py                   # CREATE: engine + SessionLocal + get_db()
    embeddings/
      encoder.py                   # CREATE: Embedder (encode + count_tokens), singleton
    llm/
      base.py                      # CREATE: LLMMessage, LLMResponse, LLMClient protocol
      fake.py                      # CREATE: FakeLLMClient (deterministic, cited)
      gemini.py                    # CREATE: GeminiClient (google-genai)
      ollama.py                    # CREATE: OllamaClient (httpx)
      factory.py                   # CREATE: get_llm_client(settings, private_mode)
    ingest/
      hashing.py                   # CREATE: normalize + content_hash
      chunking.py                  # CREATE: chunk_text (ADR-0003)
      service.py                   # CREATE: ingest_documents orchestration
    retrieval/
      fusion.py                    # CREATE: Candidate, FusedHit, rrf_fuse
      hybrid.py                    # CREATE: vector/fulltext SQL + hybrid_search
    chat/
      prompt.py                    # CREATE: SYSTEM_PROMPT, build_messages, parse_citations
      service.py                   # CREATE: chat orchestration
    schemas/
      ingest.py                    # CREATE: pydantic request/response
      chat.py                      # CREATE: pydantic request/response
    api/
      ingest.py                    # CREATE: router POST /ingest
      chat.py                      # CREATE: router POST /chat
      health.py                    # CREATE: router GET /health
  tests/
    conftest.py                    # CREATE: settings, fake embedder, db fixtures
    unit/
      test_hashing.py test_chunking.py test_fusion.py
      test_prompt.py test_llm_factory.py
    integration/                   # require Docker Postgres; skip if SECOND_BRAIN_TEST_DATABASE_URL unset
      conftest.py test_ingest.py test_retrieval.py test_chat.py test_api.py
  README.md                        # MODIFY: Phase 1 run/verify section
```

**Conventions:** one responsibility per file; pure logic (hashing, chunking, fusion, prompt,
factory) is DB-free and unit-tested; SQL and orchestration are integration-tested against a
real Postgres. Commit after each green task with a `feat:`/`test:` message.

---

## Task 1 — Dependencies & config

**Files:** Modify `backend/requirements.txt`, `backend/app/config.py`; Test
`backend/tests/unit/test_config.py`.

- [ ] **Step 1 — Add runtime deps to `requirements.txt`** (append below the Phase 0 block):

```
# Phase 1 — RAG MVP runtime
fastapi>=0.111,<1
uvicorn[standard]>=0.30,<1
sentence-transformers>=3,<4
google-genai>=0.3,<2
httpx>=0.27,<1
# dev/test
pytest>=8,<9
```

- [ ] **Step 2 — Extend `config.py`** (keep the existing `database_url`):

```python
"""Application settings."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SECOND_BRAIN_", env_file=".env",
        env_file_encoding="utf-8", extra="ignore",
    )

    database_url: str = "postgresql+psycopg://second_brain:second_brain@localhost:5432/second_brain"

    # LLM driver (ADR-0001, ADR-0007)
    llm_provider: str = "gemini"          # gemini | ollama | fake
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-1.5-flash"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # Embeddings (ADR-0002)
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # Chunking (ADR-0003)
    chunk_target_tokens: int = 512
    chunk_overlap_ratio: float = 0.15

    # Retrieval (ADR-0005)
    retrieval_k_vector: int = 20
    retrieval_k_fulltext: int = 20
    retrieval_rrf_k: int = 60
    retrieval_top_k: int = 8
    retrieval_w_vector: float = 1.0
    retrieval_w_fulltext: float = 1.0

    # Chat (ADR-0006)
    history_window: int = 6

    # API
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
```

- [ ] **Step 3 — Failing test** `tests/unit/test_config.py`:

```python
from app.config import Settings


def test_defaults():
    s = Settings()
    assert s.llm_provider == "gemini"
    assert s.embedding_dim == 384
    assert s.retrieval_top_k == 8


def test_env_override(monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_LLM_PROVIDER", "fake")
    monkeypatch.setenv("SECOND_BRAIN_RETRIEVAL_TOP_K", "3")
    s = Settings()
    assert s.llm_provider == "fake"
    assert s.retrieval_top_k == 3
```

- [ ] **Step 4 — Run** `pytest tests/unit/test_config.py -v` → PASS.
- [ ] **Step 5 — Commit** `feat(config): phase-1 settings (llm, embeddings, retrieval, cors)`.

---

## Task 2 — DB session (DB-bound)

**Files:** Create `backend/app/db/session.py`; Test `backend/tests/integration/test_session.py`.

- [ ] **Step 1 — `db/session.py`:**

```python
"""Synchronous engine + session factory (ADR-0007)."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2 — Integration test** `tests/integration/test_session.py` (skips without DB):

```python
import os
import pytest
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB")


def test_connects_and_has_vector(db_session):
    assert db_session.execute(text("SELECT 1")).scalar() == 1
    ext = db_session.execute(
        text("SELECT extname FROM pg_extension WHERE extname='vector'")).scalar()
    assert ext == "vector"
```

- [ ] **Step 3 — Run** (after `docker compose up -d db` and `alembic upgrade head`):
  `pytest tests/integration/test_session.py -v` → PASS (or SKIP if DB unset).
- [ ] **Step 4 — Commit** `feat(db): sync engine + session factory`.

---

## Task 3 — Hashing & dedupe key (DB-free)

**Files:** Create `backend/app/ingest/hashing.py`; Test `backend/tests/unit/test_hashing.py`.

- [ ] **Step 1 — Failing test:**

```python
from app.ingest.hashing import normalize, content_hash


def test_normalize_collapses_whitespace():
    assert normalize("  a\n\n b\t c ") == "a b c"


def test_hash_is_stable_and_whitespace_insensitive():
    assert content_hash("a b c") == content_hash("  a  b   c ")
    assert len(content_hash("x")) == 64
    assert content_hash("a") != content_hash("b")
```

- [ ] **Step 2 — Run** → FAIL (module missing).
- [ ] **Step 3 — Implement `ingest/hashing.py`:**

```python
"""Content hashing for dedupe (documents.content_hash, UNIQUE(source_id, content_hash))."""
from __future__ import annotations

import hashlib
import re

_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    return _WS.sub(" ", text or "").strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()
```

- [ ] **Step 4 — Run** → PASS. **Step 5 — Commit** `feat(ingest): content hashing + normalize`.

---

## Task 4 — Chunking, ADR-0003 (DB-free)

**Files:** Create `backend/app/ingest/chunking.py`; Test `backend/tests/unit/test_chunking.py`.

Token counting is **injected** (`count_tokens: Callable[[str], int]`) so unit tests use a
whitespace counter and production passes the model tokenizer (Task 5). Boundaries:
paragraphs → sentences → word-windows fallback for an oversized unit.

- [ ] **Step 1 — Failing test:**

```python
from app.ingest.chunking import chunk_text

words = lambda s: len(s.split())  # noqa: E731 — test token counter


def test_short_text_single_chunk():
    chunks = chunk_text("one two three", words, target_tokens=512)
    assert len(chunks) == 1
    assert chunks[0].content == "one two three"
    assert chunks[0].char_start == 0 and chunks[0].char_end == len("one two three")
    assert chunks[0].index == 0


def test_long_text_splits_with_overlap_and_offsets():
    text = "\n\n".join(f"para{i} " + " ".join(["w"] * 100) for i in range(6))
    chunks = chunk_text(text, words, target_tokens=120, overlap_ratio=0.15)
    assert len(chunks) > 1
    assert [c.index for c in chunks] == list(range(len(chunks)))
    for c in chunks:
        assert text[c.char_start:c.char_end] == c.content   # offsets are exact
        assert c.token_count <= 120
    # adjacent chunks overlap (start of next < end of prev)
    assert chunks[1].char_start < chunks[0].char_end


def test_single_oversized_unit_is_word_split():
    text = " ".join(["w"] * 1000)        # one sentence, no boundaries
    chunks = chunk_text(text, words, target_tokens=100, overlap_ratio=0.1)
    assert len(chunks) >= 10
    assert all(c.token_count <= 100 for c in chunks)
```

- [ ] **Step 2 — Run** → FAIL.
- [ ] **Step 3 — Implement `ingest/chunking.py`:**

```python
"""Semantic-boundary chunking — ADR-0003 (~512 tokens, ~15% overlap)."""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

_PARA = re.compile(r"\n\s*\n")
_SENT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"\S+")


@dataclass
class Chunk:
    index: int
    content: str
    char_start: int
    char_end: int
    token_count: int


def _segments(text: str) -> list[tuple[int, int]]:
    """Atomic spans on semantic boundaries: paragraphs, then sentences. Offsets into `text`."""
    spans: list[tuple[int, int]] = []
    pos = 0
    for para in _PARA.split(text):
        if not para.strip():
            pos += len(para)
            continue
        p_start = text.find(para, pos)
        p_end = p_start + len(para)
        pos = p_end
        last = p_start
        for piece in _SENT.split(text[p_start:p_end]):
            if not piece.strip():
                continue
            s_start = text.find(piece, last)
            s_end = s_start + len(piece)
            spans.append((s_start, s_end))
            last = s_end
    return spans


def _pack(units: list[tuple[int, int]], text: str, count_tokens: Callable[[str], int],
          target: int, overlap_tokens: int) -> list[tuple[int, int]]:
    """Greedily pack ordered spans up to `target` tokens, stepping back for overlap."""
    out: list[tuple[int, int]] = []
    i = 0
    while i < len(units):
        tok, j = 0, i
        while j < len(units):
            t = count_tokens(text[units[j][0]:units[j][1]])
            if tok and tok + t > target:
                break
            tok += t
            j += 1
        out.append((units[i][0], units[j - 1][1]))
        if j >= len(units):
            break
        back, k = 0, j
        while k - 1 > i and back < overlap_tokens:
            back += count_tokens(text[units[k - 1][0]:units[k - 1][1]])
            k -= 1
        i = max(k, i + 1)
    return out


def chunk_text(text: str, count_tokens: Callable[[str], int],
               target_tokens: int = 512, overlap_ratio: float = 0.15) -> list[Chunk]:
    text = text or ""
    overlap_tokens = max(0, int(target_tokens * overlap_ratio))
    units: list[tuple[int, int]] = []
    for s, e in _segments(text):
        if count_tokens(text[s:e]) <= target_tokens:
            units.append((s, e))
        else:  # oversized single unit → word-window fallback
            words = [(m.start() + s, m.end() + s) for m in _WORD.finditer(text[s:e])]
            units.extend(_pack(words, text, count_tokens, target_tokens, max(1, overlap_tokens)))
    spans = _pack(units, text, count_tokens, target_tokens, overlap_tokens)
    return [
        Chunk(idx, text[a:b], a, b, count_tokens(text[a:b]))
        for idx, (a, b) in enumerate(spans)
    ]
```

- [ ] **Step 4 — Run** → PASS. **Step 5 — Commit** `feat(ingest): semantic chunking (ADR-0003)`.

---

## Task 5 — Local embeddings encoder

**Files:** Create `backend/app/embeddings/encoder.py`; Test `backend/tests/unit/test_encoder.py`.

- [ ] **Step 1 — `embeddings/encoder.py`:**

```python
"""Local sentence-transformers encoder (ADR-0002). Lazy singleton: the model loads once."""
from __future__ import annotations

from functools import lru_cache

from app.config import settings

DIM = 384


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer  # heavy import, deferred
    return SentenceTransformer(settings.embedding_model)


class Embedder:
    model_name = settings.embedding_model
    dim = DIM

    def encode(self, texts: list[str]) -> list[list[float]]:
        vecs = _model().encode(list(texts), normalize_embeddings=True)
        return [[float(x) for x in v] for v in vecs]

    def count_tokens(self, text: str) -> int:
        return len(_model().tokenizer.tokenize(text or ""))
```

- [ ] **Step 2 — Interface test** (DB-free, network-free via monkeypatch) `test_encoder.py`:

```python
from app.embeddings import encoder


def test_encode_shape_and_norm(monkeypatch):
    class _Stub:
        def encode(self, texts, normalize_embeddings=True):
            return [[0.6, 0.8] + [0.0] * 382 for _ in texts]
    monkeypatch.setattr(encoder, "_model", lambda: _Stub())
    out = encoder.Embedder().encode(["a", "b"])
    assert len(out) == 2 and len(out[0]) == 384
    assert abs((out[0][0] ** 2 + out[0][1] ** 2) ** 0.5 - 1.0) < 1e-6
```

- [ ] **Step 3 — Optional slow test** (real model, run manually):
  `@pytest.mark.slow def test_real_model(): out = Embedder().encode(["hello"]); assert len(out[0]) == 384`.
- [ ] **Step 4 — Run** `pytest tests/unit/test_encoder.py -v` → PASS. **Step 5 — Commit**
  `feat(embeddings): local MiniLM encoder + token counter`.

---

## Task 6 — LLMClient interface + drivers (DB-free)

**Files:** Create `backend/app/llm/{base,fake,gemini,ollama,factory}.py`; Test
`backend/tests/unit/test_llm_factory.py`.

- [ ] **Step 1 — `llm/base.py`:**

```python
"""Provider-agnostic LLM seam (ADR-0001)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class LLMMessage:
    role: str          # system | user | assistant
    content: str


@dataclass
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@runtime_checkable
class LLMClient(Protocol):
    model: str

    def generate(self, messages: list[LLMMessage]) -> LLMResponse: ...
```

- [ ] **Step 2 — `llm/fake.py`** (deterministic, cites whatever markers appear in context):

```python
import re
from app.llm.base import LLMClient, LLMMessage, LLMResponse


class FakeLLMClient:
    model = "fake"

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        markers = "".join(sorted(set(re.findall(r"\[\d+\]", user)),
                                 key=lambda m: int(m.strip("[]"))))[:6]
        text = f"(fake) answer grounded in context {markers}".strip()
        return LLMResponse(text=text, model=self.model,
                           prompt_tokens=0, completion_tokens=0, total_tokens=0)


_: LLMClient = FakeLLMClient()  # structural conformance check
```

- [ ] **Step 3 — `llm/gemini.py`** (google-genai; verify the call shape against the installed
  SDK version at implementation time):

```python
from app.llm.base import LLMMessage, LLMResponse


class GeminiClient:
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        from google import genai
        self._genai = genai
        self._client = genai.Client(api_key=api_key)
        self.model = model

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        from google.genai import types
        system = "\n\n".join(m.content for m in messages if m.role == "system") or None
        contents = [
            types.Content(role="user" if m.role == "user" else "model",
                          parts=[types.Part(text=m.content)])
            for m in messages if m.role != "system"
        ]
        resp = self._client.models.generate_content(
            model=self.model, contents=contents,
            config=types.GenerateContentConfig(system_instruction=system),
        )
        u = getattr(resp, "usage_metadata", None)
        return LLMResponse(
            text=resp.text or "", model=self.model,
            prompt_tokens=getattr(u, "prompt_token_count", None),
            completion_tokens=getattr(u, "candidates_token_count", None),
            total_tokens=getattr(u, "total_token_count", None),
        )
```

- [ ] **Step 4 — `llm/ollama.py`** (httpx, non-streaming chat):

```python
import httpx
from app.llm.base import LLMMessage, LLMResponse


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.1"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        payload = {"model": self.model, "stream": False,
                   "messages": [{"role": m.role, "content": m.content} for m in messages]}
        r = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=120.0)
        r.raise_for_status()
        data = r.json()
        return LLMResponse(text=data["message"]["content"], model=self.model,
                           prompt_tokens=data.get("prompt_eval_count"),
                           completion_tokens=data.get("eval_count"))
```

- [ ] **Step 5 — `llm/factory.py`:**

```python
from app.config import Settings
from app.llm.base import LLMClient
from app.llm.fake import FakeLLMClient


def get_llm_client(settings: Settings, *, private_mode: bool = False) -> LLMClient:
    provider = "ollama" if private_mode else settings.llm_provider
    if provider == "fake":
        return FakeLLMClient()
    if provider == "ollama":
        from app.llm.ollama import OllamaClient
        return OllamaClient(settings.ollama_base_url, settings.ollama_model)
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("SECOND_BRAIN_GEMINI_API_KEY is required for the gemini provider")
        from app.llm.gemini import GeminiClient
        return GeminiClient(settings.gemini_api_key, settings.gemini_model)
    raise ValueError(f"unknown llm_provider: {provider}")
```

- [ ] **Step 6 — Test** `test_llm_factory.py`:

```python
import pytest
from app.config import Settings
from app.llm.base import LLMMessage
from app.llm.factory import get_llm_client
from app.llm.fake import FakeLLMClient


def test_factory_selects_fake():
    assert isinstance(get_llm_client(Settings(llm_provider="fake")), FakeLLMClient)


def test_private_mode_forces_ollama():
    c = get_llm_client(Settings(llm_provider="gemini"), private_mode=True)
    assert c.model  # OllamaClient, not Gemini
    assert c.__class__.__name__ == "OllamaClient"


def test_gemini_requires_key():
    with pytest.raises(RuntimeError):
        get_llm_client(Settings(llm_provider="gemini", gemini_api_key=None))


def test_fake_cites_context_markers():
    out = FakeLLMClient().generate([LLMMessage("user", "ctx [1] and [2] then question")])
    assert "[1]" in out.text and "[2]" in out.text
```

- [ ] **Step 7 — Run** → PASS. **Step 8 — Commit** `feat(llm): LLMClient seam + gemini/ollama/fake`.

---

## Task 7 — RRF fusion (DB-free)

**Files:** Create `backend/app/retrieval/fusion.py`; Test `backend/tests/unit/test_fusion.py`.

- [ ] **Step 1 — Failing test:**

```python
from app.retrieval.fusion import Candidate, rrf_fuse


def test_overlap_ranks_first():
    v = [Candidate(1, 0.9, 1), Candidate(2, 0.8, 2)]
    f = [Candidate(2, 5.0, 1), Candidate(3, 4.0, 2)]
    hits = rrf_fuse(v, f, rrf_k=60, top_k=3)
    assert hits[0].chunk_id == 2 and hits[0].method == "hybrid"
    by_id = {h.chunk_id: h for h in hits}
    assert by_id[1].method == "vector" and by_id[1].fulltext_score is None
    assert by_id[3].method == "fulltext" and by_id[3].vector_score is None
    assert [h.rank for h in hits] == [1, 2, 3]


def test_weights_and_topk():
    v = [Candidate(1, 0.9, 1)]
    f = [Candidate(2, 9.9, 1)]
    hits = rrf_fuse(v, f, w_vector=10.0, w_fulltext=1.0, top_k=1)
    assert len(hits) == 1 and hits[0].chunk_id == 1
```

- [ ] **Step 2 — Run** → FAIL.
- [ ] **Step 3 — Implement `retrieval/fusion.py`:**

```python
"""Reciprocal Rank Fusion of two candidate lists — ADR-0005."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Candidate:
    chunk_id: int
    score: float       # modality score: cosine similarity OR ts_rank_cd
    rank: int          # 1-based within its list


@dataclass
class FusedHit:
    chunk_id: int
    score: float                       # fused RRF score
    method: str                        # vector | fulltext | hybrid
    vector_score: float | None = None
    fulltext_score: float | None = None
    rank: int = 0                       # 1-based, set after sort


def rrf_fuse(vector: list[Candidate], fulltext: list[Candidate], *,
             rrf_k: int = 60, w_vector: float = 1.0, w_fulltext: float = 1.0,
             top_k: int = 8) -> list[FusedHit]:
    vmap = {c.chunk_id: c for c in vector}
    fmap = {c.chunk_id: c for c in fulltext}
    fused: dict[int, float] = {}
    for c in vector:
        fused[c.chunk_id] = fused.get(c.chunk_id, 0.0) + w_vector / (rrf_k + c.rank)
    for c in fulltext:
        fused[c.chunk_id] = fused.get(c.chunk_id, 0.0) + w_fulltext / (rrf_k + c.rank)

    hits: list[FusedHit] = []
    for cid, s in fused.items():
        in_v, in_f = cid in vmap, cid in fmap
        method = "hybrid" if in_v and in_f else ("vector" if in_v else "fulltext")
        hits.append(FusedHit(
            chunk_id=cid, score=s, method=method,
            vector_score=vmap[cid].score if in_v else None,
            fulltext_score=fmap[cid].score if in_f else None,
        ))
    hits.sort(key=lambda h: (h.score, h.chunk_id), reverse=True)
    hits = hits[:top_k]
    for i, h in enumerate(hits, start=1):
        h.rank = i
    return hits
```

- [ ] **Step 4 — Run** → PASS. **Step 5 — Commit** `feat(retrieval): RRF fusion (ADR-0005)`.

---

## Task 8 — Prompt building & citation parsing (DB-free)

**Files:** Create `backend/app/chat/prompt.py`; Test `backend/tests/unit/test_prompt.py`.

- [ ] **Step 1 — Implement `chat/prompt.py`:**

```python
"""Prompt template + citation parsing — ADR-0006."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.llm.base import LLMMessage

PROMPT_VERSION = "rag-v1"
REFUSAL_TEXT = "I don't have anything in your notes about that yet."
SYSTEM_PROMPT = (
    "You are Second Brain, a personal assistant. Answer ONLY using the numbered context "
    "below. Cite every claim with bracketed markers like [1], [2] that refer to the context "
    "items you used. If the context does not contain the answer, say so plainly. Never invent "
    "facts or citations that are not in the context."
)

_MARKER = re.compile(r"\[(\d+)\]")


@dataclass
class ContextItem:
    marker: int                 # 1-based
    source_name: str
    document_title: str
    content: str


def build_context_block(items: list[ContextItem]) -> str:
    return "\n\n".join(
        f"[{it.marker}] (source: {it.source_name} · doc: {it.document_title})\n{it.content}"
        for it in items
    )


def build_messages(question: str, items: list[ContextItem],
                   history: list[LLMMessage] | None = None) -> list[LLMMessage]:
    msgs = [LLMMessage("system", SYSTEM_PROMPT)]
    msgs += history or []
    block = build_context_block(items)
    msgs.append(LLMMessage("user", f"Context:\n{block}\n\nQuestion: {question}"))
    return msgs


def parse_citations(answer: str, n_items: int) -> list[int]:
    """Ordered, de-duplicated, in-range markers the model actually used."""
    seen: list[int] = []
    for m in _MARKER.findall(answer):
        i = int(m)
        if 1 <= i <= n_items and i not in seen:
            seen.append(i)
    return seen
```

- [ ] **Step 2 — Test** `test_prompt.py`:

```python
from app.chat.prompt import ContextItem, build_messages, parse_citations, SYSTEM_PROMPT


def test_build_messages_numbers_context_and_includes_history():
    from app.llm.base import LLMMessage
    items = [ContextItem(1, "Notes", "Doc A", "alpha"), ContextItem(2, "Notes", "Doc B", "beta")]
    msgs = build_messages("q?", items, history=[LLMMessage("user", "earlier")])
    assert msgs[0].role == "system" and msgs[0].content == SYSTEM_PROMPT
    assert msgs[1].content == "earlier"
    assert "[1]" in msgs[-1].content and "[2]" in msgs[-1].content and "Question: q?" in msgs[-1].content


def test_parse_citations_dedup_and_range():
    assert parse_citations("uses [2] and [1] and [2] and [9]", n_items=3) == [2, 1]
```

- [ ] **Step 3 — Run** → PASS. **Step 4 — Commit** `feat(chat): prompt template + citations (ADR-0006)`.

---

## Task 9 — Ingest service (DB-bound)

**Files:** Create `backend/app/ingest/service.py`; Test `backend/tests/integration/test_ingest.py`.
The service takes an injected `embedder` (real `Embedder` in prod; a fast deterministic fake in
tests — see `conftest.py`, Task 12).

- [ ] **Step 1 — Implement `ingest/service.py`:**

```python
"""Inline ingest: find-or-create source → dedupe → chunk → embed → store (ADR-0007)."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Chunk, Document, DocumentTag, Embedding, Source, Tag
from app.ingest.chunking import chunk_text
from app.ingest.hashing import content_hash


@dataclass
class SourceSpec:
    type: str
    name: str
    uri: str | None = None
    config: dict = field(default_factory=dict)


@dataclass
class DocumentInput:
    title: str
    content: str
    external_id: str | None = None
    content_type: str | None = "text/plain"
    metadata: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


@dataclass
class DocumentResult:
    document_id: int | None
    title: str
    status: str                 # embedded | duplicate | failed
    content_hash: str
    chunk_count: int = 0
    embedded_count: int = 0
    duplicate_of: int | None = None
    error: str | None = None


@dataclass
class IngestResult:
    source_id: int
    documents: list[DocumentResult]


def _get_or_create_source(db: Session, spec: SourceSpec) -> Source:
    src = db.scalar(select(Source).where(Source.type == spec.type, Source.name == spec.name))
    if src:
        return src
    src = Source(type=spec.type, name=spec.name, uri=spec.uri, config=spec.config)
    db.add(src)
    db.flush()
    return src


def _get_or_create_tags(db: Session, names: list[str]) -> list[Tag]:
    tags: list[Tag] = []
    for name in dict.fromkeys(n.strip() for n in names if n.strip()):
        tag = db.scalar(select(Tag).where(Tag.name == name))
        if not tag:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()
        tags.append(tag)
    return tags


def ingest_documents(db: Session, embedder, *, source: SourceSpec,
                     documents: list[DocumentInput]) -> IngestResult:
    src = _get_or_create_source(db, source)
    results: list[DocumentResult] = []

    for doc_in in documents:
        chash = content_hash(doc_in.content)
        existing = db.scalar(
            select(Document).where(Document.source_id == src.id,
                                   Document.content_hash == chash))
        if existing:
            results.append(DocumentResult(existing.id, doc_in.title, "duplicate",
                                          chash, duplicate_of=existing.id))
            continue
        try:
            doc = Document(
                source_id=src.id, title=doc_in.title, external_id=doc_in.external_id,
                content_type=doc_in.content_type, content_hash=chash,
                raw_text=doc_in.content, metadata_=doc_in.metadata, status="pending",
            )
            db.add(doc)
            db.flush()
            for tag in _get_or_create_tags(db, doc_in.tags):
                db.add(DocumentTag(document_id=doc.id, tag_id=tag.id))

            pieces = chunk_text(doc_in.content, embedder.count_tokens,
                                settings.chunk_target_tokens, settings.chunk_overlap_ratio)
            vectors = embedder.encode([p.content for p in pieces]) if pieces else []
            for piece, vec in zip(pieces, vectors):
                chunk = Chunk(document_id=doc.id, chunk_index=piece.index,
                              content=piece.content, token_count=piece.token_count,
                              char_start=piece.char_start, char_end=piece.char_end)
                db.add(chunk)
                db.flush()
                db.add(Embedding(chunk_id=chunk.id, model=embedder.model_name,
                                 dim=embedder.dim, embedding=vec))

            from datetime import datetime, timezone
            doc.status = "embedded"
            doc.ingested_at = datetime.now(timezone.utc)
            db.flush()
            results.append(DocumentResult(doc.id, doc_in.title, "embedded", chash,
                                          chunk_count=len(pieces), embedded_count=len(vectors)))
        except Exception as exc:  # one bad doc must not fail the batch
            db.rollback()
            results.append(DocumentResult(None, doc_in.title, "failed", chash, error=str(exc)))

    db.commit()
    return IngestResult(source_id=src.id, documents=results)
```

> **Note for the implementer:** the per-doc `db.rollback()` in the `except` discards the whole
> uncommitted unit of work, so successful earlier docs in the same batch would be lost. During
> implementation, switch to a **per-document `SAVEPOINT`** (`with db.begin_nested():` around
> each document, `db.commit()` once at the end) so a single failure rolls back only that doc.
> This is the intended design; the simplified `try/except` above is pseudocode for the happy
> path — implement the savepoint version and cover it with `test_partial_failure`.

- [ ] **Step 2 — Integration test** `test_ingest.py` (uses `db_session` + `fake_embedder`):

```python
import os, pytest
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB")


def test_ingest_creates_rows_and_dedupes(db_session, fake_embedder):
    spec = SourceSpec(type="manual", name="T")
    docs = [DocumentInput(title="A", content="alpha beta. " * 50, tags=["x"])]
    r1 = ingest_documents(db_session, fake_embedder, source=spec, documents=docs)
    assert r1.documents[0].status == "embedded"
    assert r1.documents[0].chunk_count >= 1
    assert r1.documents[0].embedded_count == r1.documents[0].chunk_count

    r2 = ingest_documents(db_session, fake_embedder, source=spec, documents=docs)
    assert r2.documents[0].status == "duplicate"
    assert r2.source_id == r1.source_id            # source reused
```

- [ ] **Step 3 — Run** (DB up) → PASS. **Step 4 — Commit** `feat(ingest): inline ingest service`.

---

## Task 10 — Hybrid retrieval SQL (DB-bound)

**Files:** Create `backend/app/retrieval/hybrid.py`; Test `backend/tests/integration/test_retrieval.py`.

- [ ] **Step 1 — Implement `retrieval/hybrid.py`:**

```python
"""Vector + full-text candidate queries and hybrid search (ADR-0005)."""
from __future__ import annotations

from dataclasses import dataclass

from pgvector.sqlalchemy import Vector
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.retrieval.fusion import Candidate, FusedHit, rrf_fuse

_FILTER = """
  AND (:source_ids IS NULL OR d.source_id = ANY(:source_ids))
  AND (:tags IS NULL OR EXISTS (
        SELECT 1 FROM document_tags dt JOIN tags t ON t.id = dt.tag_id
        WHERE dt.document_id = d.id AND t.name = ANY(:tags)))
"""

_VECTOR_SQL = text(f"""
    SELECT e.chunk_id AS chunk_id,
           1 - (e.embedding <=> :qvec) AS score,
           row_number() OVER (ORDER BY e.embedding <=> :qvec) AS rank
    FROM embeddings e
    JOIN chunks c    ON c.id = e.chunk_id
    JOIN documents d ON d.id = c.document_id
    WHERE e.model = :model {_FILTER}
    ORDER BY e.embedding <=> :qvec
    LIMIT :k
""").bindparams(bindparam("qvec", type_=Vector(384)))

_FULLTEXT_SQL = text(f"""
    SELECT c.id AS chunk_id,
           ts_rank_cd(c.tsv, query) AS score,
           row_number() OVER (ORDER BY ts_rank_cd(c.tsv, query) DESC) AS rank
    FROM chunks c
    JOIN documents d ON d.id = c.document_id,
         websearch_to_tsquery('english', :q) query
    WHERE c.tsv @@ query {_FILTER}
    ORDER BY score DESC
    LIMIT :k
""")


@dataclass
class DisplayChunk:
    chunk_id: int
    content: str
    document_id: int
    document_title: str
    source_id: int
    source_name: str
    char_start: int | None
    char_end: int | None


def _candidates(db, sql, params) -> list[Candidate]:
    return [Candidate(int(r.chunk_id), float(r.score), int(r.rank))
            for r in db.execute(sql, params).all()]


def hybrid_search(db: Session, embedder, settings: Settings, query: str,
                  *, top_k: int | None = None, source_ids=None, tags=None
                  ) -> tuple[list[FusedHit], dict]:
    qvec = embedder.encode([query])[0]
    common = {"source_ids": source_ids, "tags": tags}
    vec = _candidates(db, _VECTOR_SQL,
                      {**common, "qvec": qvec, "model": embedder.model_name,
                       "k": settings.retrieval_k_vector})
    fts = _candidates(db, _FULLTEXT_SQL,
                      {**common, "q": query, "k": settings.retrieval_k_fulltext})
    hits = rrf_fuse(vec, fts, rrf_k=settings.retrieval_rrf_k,
                    w_vector=settings.retrieval_w_vector,
                    w_fulltext=settings.retrieval_w_fulltext,
                    top_k=top_k or settings.retrieval_top_k)
    meta = {"method": "hybrid", "candidates_vector": len(vec),
            "candidates_fulltext": len(fts), "fused_returned": len(hits)}
    return hits, meta


def load_display_chunks(db: Session, chunk_ids: list[int]) -> dict[int, DisplayChunk]:
    if not chunk_ids:
        return {}
    rows = db.execute(text("""
        SELECT c.id, c.content, c.char_start, c.char_end,
               d.id AS document_id, d.title AS document_title,
               s.id AS source_id, s.name AS source_name
        FROM chunks c JOIN documents d ON d.id = c.document_id
                      JOIN sources s   ON s.id = d.source_id
        WHERE c.id = ANY(:ids)
    """), {"ids": chunk_ids}).all()
    return {r.id: DisplayChunk(r.id, r.content, r.document_id, r.document_title,
                               r.source_id, r.source_name, r.char_start, r.char_end)
            for r in rows}
```

- [ ] **Step 2 — Integration test** `test_retrieval.py`: ingest two docs (one matching a term
  semantically, one lexically), call `hybrid_search`, assert the relevant chunk ranks first and
  `meta["candidates_*"]` are populated. Use `fake_embedder` whose `encode` returns a vector keyed
  off keyword presence so similarity is deterministic.
- [ ] **Step 3 — Run** (DB up) → PASS. **Step 4 — Commit** `feat(retrieval): hybrid vector+fulltext search`.

---

## Task 11 — Chat service (DB-bound)

**Files:** Create `backend/app/chat/service.py`; Test `backend/tests/integration/test_chat.py`.

- [ ] **Step 1 — Implement `chat/service.py`** (orchestration; persists conversation, messages,
  retrievals; short-circuits on empty retrieval per ADR-0006):

```python
"""Chat orchestration — retrieve → prompt → generate → persist (ADR-0006/0007)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chat.prompt import ContextItem, REFUSAL_TEXT, build_messages, parse_citations
from app.config import Settings
from app.db.models import Conversation, Message, Retrieval
from app.llm.base import LLMMessage
from app.retrieval.hybrid import hybrid_search, load_display_chunks


@dataclass
class Citation:
    marker: int
    chunk_id: int
    document_id: int
    document_title: str
    source_id: int
    source_name: str
    score: float | None
    vector_score: float | None
    fulltext_score: float | None
    method: str
    snippet: str | None = None
    char_start: int | None = None
    char_end: int | None = None


@dataclass
class ChatResult:
    conversation_id: int
    message_id: int
    answer: str
    citations: list[Citation]
    usage: dict
    model: str | None
    latency_ms: int
    retrieval: dict = field(default_factory=dict)


def _history(db: Session, conversation_id: int, window: int) -> list[LLMMessage]:
    rows = db.scalars(
        select(Message).where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id.desc()).limit(window)).all()
    return [LLMMessage(m.role, m.content) for m in reversed(rows)]


def chat(db: Session, embedder, llm, settings: Settings, *, message: str,
         conversation_id: int | None = None, top_k: int | None = None,
         filters: dict | None = None, include_chunks: bool = True) -> ChatResult:
    filters = filters or {}
    if conversation_id is None:
        conv = Conversation(title=message[:80])
        db.add(conv)
        db.flush()
        conversation_id = conv.id

    history = _history(db, conversation_id, settings.history_window)
    db.add(Message(conversation_id=conversation_id, role="user", content=message))
    db.flush()

    hits, meta = hybrid_search(db, embedder, settings, message,
                               top_k=top_k, source_ids=filters.get("source_ids"),
                               tags=filters.get("tags"))

    # Zero-context short-circuit — no LLM call (ADR-0006)
    if not hits:
        assistant = Message(conversation_id=conversation_id, role="assistant",
                            content=REFUSAL_TEXT, model=None)
        db.add(assistant)
        db.commit()
        return ChatResult(conversation_id, assistant.id, REFUSAL_TEXT, [],
                          {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                          None, 0, {**meta, "fused_returned": 0})

    display = load_display_chunks(db, [h.chunk_id for h in hits])
    items = [ContextItem(i + 1, display[h.chunk_id].source_name,
                         display[h.chunk_id].document_title, display[h.chunk_id].content)
             for i, h in enumerate(hits)]
    messages = build_messages(message, items, history)

    started = time.perf_counter()
    resp = llm.generate(messages)
    latency_ms = int((time.perf_counter() - started) * 1000)

    cited = parse_citations(resp.text, len(items))
    usage = {"prompt_tokens": resp.prompt_tokens, "completion_tokens": resp.completion_tokens,
             "total_tokens": resp.total_tokens}
    assistant = Message(conversation_id=conversation_id, role="assistant", content=resp.text,
                        model=resp.model, token_usage=usage, latency_ms=latency_ms)
    db.add(assistant)
    db.flush()

    citations: list[Citation] = []
    for i, h in enumerate(hits):
        marker = i + 1
        db.add(Retrieval(message_id=assistant.id, chunk_id=h.chunk_id, rank=h.rank,
                         score=h.score, vector_score=h.vector_score,
                         fulltext_score=h.fulltext_score, method=h.method))
        if marker in cited:
            dc = display[h.chunk_id]
            citations.append(Citation(
                marker=marker, chunk_id=h.chunk_id, document_id=dc.document_id,
                document_title=dc.document_title, source_id=dc.source_id,
                source_name=dc.source_name, score=h.score, vector_score=h.vector_score,
                fulltext_score=h.fulltext_score, method=h.method,
                snippet=dc.content if include_chunks else None,
                char_start=dc.char_start if include_chunks else None,
                char_end=dc.char_end if include_chunks else None))

    db.commit()
    return ChatResult(conversation_id, assistant.id, resp.text, citations, usage,
                      resp.model, latency_ms, meta)
```

- [ ] **Step 2 — Integration test** `test_chat.py` (ingest → chat with `fake` LLM):

```python
import os, pytest
from app.chat.service import chat
from app.config import Settings
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents
from app.llm.fake import FakeLLMClient

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB")


def test_chat_persists_and_cites(db_session, fake_embedder):
    ingest_documents(db_session, fake_embedder, source=SourceSpec("manual", "T"),
                     documents=[DocumentInput(title="HNSW", content="HNSW tuning m ef_construction. " * 20)])
    r = chat(db_session, fake_embedder, FakeLLMClient(), Settings(),
             message="What about HNSW tuning?")
    assert r.message_id and r.conversation_id
    assert r.retrieval["fused_returned"] >= 1
    assert r.answer  # fake driver returns a non-empty cited answer


def test_chat_empty_corpus_refuses(db_session, fake_embedder):
    r = chat(db_session, fake_embedder, FakeLLMClient(), Settings(), message="anything?")
    assert r.citations == [] and r.model is None
```

- [ ] **Step 3 — Run** (DB up) → PASS. **Step 4 — Commit** `feat(chat): chat service + persistence`.

---

## Task 12 — FastAPI app, schemas, routers, test fixtures

**Files:** Create `backend/app/{deps,main}.py`, `app/schemas/{ingest,chat}.py`,
`app/api/{ingest,chat,health}.py`, `tests/conftest.py`, `tests/integration/conftest.py`,
`tests/integration/test_api.py`.

- [ ] **Step 1 — `app/deps.py`** (FastAPI dependencies):

```python
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
```

- [ ] **Step 2 — `app/schemas/ingest.py` and `app/schemas/chat.py`** — pydantic v2 models that
  mirror the ADR-0007 JSON exactly (`IngestRequest{source, documents[]}` →
  `IngestResponse{source_id, documents[], summary}`; `ChatRequest{message, conversation_id,
  top_k, filters, options}` → `ChatResponse{conversation_id, message_id, answer, citations[],
  usage, model, latency_ms, retrieval}`). Field names match the service dataclasses so mapping
  is mechanical.

- [ ] **Step 3 — `app/api/health.py`, `app/api/ingest.py`, `app/api/chat.py`** — thin routers
  that translate request → service call → response. `ingest` maps `IngestRequest` to
  `SourceSpec`/`DocumentInput`, calls `ingest_documents`, builds the `summary`. `chat` reads
  `options.private_mode`, builds the `llm` via `get_llm_client(settings, private_mode=...)`,
  calls `chat(...)`, maps `ChatResult` → `ChatResponse`. `health` checks `SELECT 1` and whether
  the embedder singleton is loaded.

- [ ] **Step 4 — `app/main.py`:**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, health, ingest
from app.config import settings

app = FastAPI(title="Second Brain API", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origins,
    allow_methods=["*"], allow_headers=["*"], allow_credentials=True,
)
app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(chat.router)
```

- [ ] **Step 5 — `tests/conftest.py`** — a `fake_embedder` fixture (deterministic 384-d vectors
  derived from token hashing so cosine similarity is stable; `count_tokens = len(text.split())`;
  `model_name`/`dim` set) and a `settings` fixture forcing `llm_provider="fake"`.

- [ ] **Step 6 — `tests/integration/conftest.py`** — a `db_session` fixture that connects to
  `SECOND_BRAIN_TEST_DATABASE_URL`, runs each test inside a transaction it rolls back
  (`connection.begin()` + `Session(bind=connection)` + `transaction.rollback()` in teardown),
  and a FastAPI `client` fixture that overrides `get_db`/`get_embedder`/`get_settings` with the
  test session + fake embedder + fake-provider settings.

- [ ] **Step 7 — `tests/integration/test_api.py`** — `TestClient` happy paths:

```python
import os, pytest
pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB")


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_ingest_then_chat(client):
    ing = client.post("/ingest", json={
        "source": {"type": "manual", "name": "My Notes"},
        "documents": [{"title": "HNSW", "content": "HNSW tuning m ef_construction. " * 20,
                       "tags": ["ml"]}]})
    assert ing.status_code == 200
    body = ing.json()
    assert body["summary"]["embedded"] == 1 and body["summary"]["chunks_created"] >= 1

    chat = client.post("/chat", json={"message": "How do I tune HNSW?", "top_k": 5})
    assert chat.status_code == 200
    cb = chat.json()
    assert cb["conversation_id"] and cb["message_id"]
    assert cb["retrieval"]["fused_returned"] >= 1
```

- [ ] **Step 8 — Run** `pytest -q` (unit always; integration when DB up) → PASS. **Step 9 —
  Commit** `feat(api): FastAPI /health /ingest /chat + test harness`.

---

## Task 13 — Docs: README run/verify + PROGRESS

**Files:** Modify `backend/README.md`, `docs/PROGRESS.md`.

- [ ] **Step 1 — Add a "Phase 1 — run & verify" section to `backend/README.md`:**

```bash
# 0) DB-free: unit tests + lint (no Docker needed)
cd backend && .\.venv\Scripts\Activate.ps1
pytest tests/unit -v

# 1) Bring up Postgres + pgvector and migrate
docker compose up -d db          # from repo root
alembic upgrade head

# 2) Point tests at the DB and run the full suite
$env:SECOND_BRAIN_TEST_DATABASE_URL = $env:SECOND_BRAIN_DATABASE_URL
$env:SECOND_BRAIN_LLM_PROVIDER = "fake"
pytest -v

# 3) Run the API (fake LLM → no key needed for a smoke)
uvicorn app.main:app --reload
#   POST /ingest a couple of notes, then POST /chat — see /docs for the schema
#   For real answers: set SECOND_BRAIN_LLM_PROVIDER=gemini and SECOND_BRAIN_GEMINI_API_KEY=...
```

- [ ] **Step 2 — Flip `docs/PROGRESS.md` Phase 1 → ✅** with a dated session log entry (what
  shipped, how verified, what's deferred).
- [ ] **Step 3 — Commit** `docs: phase-1 run/verify + progress`.

---

## Self-review (run against the spec + ADRs)

**Spec coverage:**
- `LLMClient` Gemini/Ollama/fake, config-selectable → Tasks 1, 6 ✅
- Local MiniLM-384 embeddings on ingest → Task 5, 9 ✅; query embedded at chat time → Task 10 ✅
- `/ingest` chunk (ADR-0003) + dedupe (content_hash) + store → Tasks 3, 4, 9 ✅
- `/chat` hybrid retrieval (pgvector + full-text) + RRF (ADR-0005) → Tasks 7, 10 ✅
- Cited answer (ADR-0006) → Task 8, 11 ✅; persists conversations/messages/retrievals → Task 11 ✅
- API contracts frozen (ADR-0007) → Task 12 ✅
- Tests alongside code (pytest unit + integration vs real Postgres) → every task ✅
- Ends runnable with run/verify instructions → Task 13 ✅

**Known sharp edges to handle during execution (not placeholders — flagged decisions):**
1. **Per-document failure isolation** in ingest needs `begin_nested()` SAVEPOINTs, not a bare
   `rollback()` (noted inline in Task 9).
2. **pgvector bind**: the query vector binds via `bindparam("qvec", type_=Vector(384))`; if the
   installed pgvector/SQLAlchemy versions need a different bind, cast `CAST(:qvec AS vector)` and
   pass `str(list(qvec))`.
3. **google-genai call shape** (`Client.models.generate_content`, `system_instruction`,
   `usage_metadata`) must be verified against the version that actually installs; isolate any
   change inside `gemini.py` only.
4. **`Document.metadata_`** is the ORM attribute for the `metadata` column — use `metadata_=` in
   constructors (already done in Task 9).

---

## Execution handoff

Plan complete, saved to `docs/phase-1-plan.md`. When you're ready to build, two options:

1. **Subagent-driven (recommended)** — dispatch a fresh subagent per task with a review
   checkpoint between tasks (`superpowers:subagent-driven-development`). Tasks 1, 3–8 run with no
   Docker; gate Tasks 2, 9–12 on `docker compose up -d db` + `alembic upgrade head`.
2. **Inline execution** — implement task-by-task in one session with checkpoints
   (`superpowers:executing-plans`).

**Recommended order:** 1 → 3 → 4 → 7 → 8 → 6 → 5 (DB-free, no Docker), then 2 → 9 → 10 → 11 → 12
once Docker Desktop is installed, then 13. CI runs Tasks 1,3–8 always and 9–12 against a
service-container Postgres with `SECOND_BRAIN_LLM_PROVIDER=fake`.
