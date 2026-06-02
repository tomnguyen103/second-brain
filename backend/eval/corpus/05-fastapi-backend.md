# FastAPI backend

The backend is a Python FastAPI service using synchronous SQLAlchemy 2.0 over psycopg3. It
exposes a small REST surface: `POST /ingest` accepts documents and runs the inline ingest
pipeline (chunk, embed, store), `POST /chat` answers a question with cited retrieval-augmented
generation, `GET /search` runs hybrid search directly, and `GET /conversations` plus
`POST /feedback` back the chat history and thumbs. Requests and responses are validated with
Pydantic v2 schemas. Generation goes through one `LLMClient` interface so the Gemini Flash
driver can be swapped for a local Ollama "private mode" by configuration alone.
