# Architecture Decision Records

Each ADR captures one real decision: context, the decision, consequences, and the alternatives
rejected. Format is lightweight [MADR](https://adr.github.io/madr/). Newest decisions supersede
older ones explicitly; we don't edit history.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-llm-driver-local-vs-hosted.md) | LLM driver: hosted Gemini Flash default, local Ollama behind one interface | Accepted |
| [0002](0002-embeddings-storage-and-model.md) | Embeddings: separate table, single fixed model `vector(384)` | Accepted |
| [0003](0003-chunking-strategy.md) | Chunking: ~512 tokens, ~15% overlap, semantic-boundary split | Accepted |
| [0004](0004-pipeline-trigger-jobs-vs-notify.md) | Pipeline trigger: durable `jobs` table + `LISTEN/NOTIFY` wake-up | Accepted |
| [0005](0005-hybrid-retrieval-rrf.md) | Hybrid retrieval: pgvector + full-text, fused with Reciprocal Rank Fusion | Accepted |
| [0006](0006-prompt-and-citation-contract.md) | Prompt template, citation contract, and grounding policy | Accepted |
| [0007](0007-phase1-api-and-execution-model.md) | Phase 1 API surface and execution model | Accepted |
| [0008](0008-evaluation-and-mlflow.md) | Evaluation methodology + MLflow tracking (local file store) | Accepted |
| [0009](0009-prompt-versioning-ab-rollback.md) | Prompt versioning, A/B, and rollback (in-code registry + env-var selection) | Accepted |
| [0010](0010-mcp-server-and-agentic-actions.md) | MCP server (FastMCP/stdio) + agentic actions: search, tasks, digest, research-this-topic | Accepted |
| [0011](0011-vps-provider.md) | VPS provider: Oracle Always Free (Singapore) primary, Contabo SG paid fallback | Accepted |
| [0012](0012-productionization-and-data-governance.md) | Productionization + data governance: RLS, audit, retention, GDPR erasure, metrics, eval-gated CI, PgBouncer | Accepted |
| [0013](0013-briefing-scheduling-and-worker.md) | Daily briefing: durable poll-based worker, OS-cron scheduling, store-and-display, briefings table | Accepted |
| [0014](0014-kubernetes-learning-track.md) | Kubernetes learning track on local kind (manifests + HPA + ingress + CI/CD), then torn down | Accepted |
| [0015](0015-local-first-obsidian-memory.md) | Local-first Obsidian memory with a manual NotebookLM bridge | Accepted |
