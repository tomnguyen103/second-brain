# Postgres full-text search

Postgres provides keyword search through a `tsvector` column that stores lexemes (normalized,
stemmed tokens) for each chunk. A GIN index over the tsvector makes matching fast. Queries are
parsed with `websearch_to_tsquery`, which accepts natural search syntax, and matches are scored
and ordered with `ts_rank_cd`, a cover-density ranking that rewards query terms appearing close
together. Full-text search is exact and lexical — great for names, identifiers, and rare terms
the embedding model may blur — which is exactly why we fuse it with vector search rather than
relying on either alone.
