# Agentic RAG opt-in

Agentic RAG is an optional read-only chat mode. It is disabled by default with
`SECOND_BRAIN_AGENTIC_RAG_ENABLED=false` and requires a request with `options.agentic=true` after
the operator enables it. The graph plans bounded subqueries, runs the existing hybrid retriever,
deduplicates evidence, and answers through the same citation validator as regular RAG. Streaming is
not available for agentic requests, because unvalidated provider text must not be emitted before
citation validation. Regular RAG remains the default until the expanded eval set shows a clear
quality win for agentic mode.
