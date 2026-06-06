# Data governance controls

Second Brain uses a single-owner security model. Personal-data routes require
`SECOND_BRAIN_API_TOKEN` in production, while destructive data operations also require
`SECOND_BRAIN_ADMIN_TOKEN` sent as `X-Second-Brain-Admin-Token`. Governance features include RLS
policies, an audit log, source export, source erasure, and a retention purge that nulls old
`documents.raw_text`. Retention does not delete searchable chunks; full erasure happens at the
source level and cascades through documents, chunks, embeddings, retrieval rows, and related data.
