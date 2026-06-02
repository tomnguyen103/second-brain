# HNSW index tuning

pgvector builds an HNSW (Hierarchical Navigable Small World) graph index for approximate
nearest-neighbor vector search. Three knobs matter. At build time, `m` sets how many
neighbors each node keeps (higher m = better recall, larger index, slower build), and
`ef_construction` sets how wide the search is while building (higher = better recall, slower
build). At query time, `ef_search` controls how many candidates are explored: raising
`ef_search` improves recall but increases query latency. The practical workflow is to fix m
and ef_construction at index creation, then tune `ef_search` to trade recall against latency,
measuring both with EXPLAIN ANALYZE on a representative query set.
