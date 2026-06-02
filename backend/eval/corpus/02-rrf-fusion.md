# Reciprocal rank fusion

Reciprocal Rank Fusion (RRF) merges two ranked candidate lists — here the vector-similarity
list and the full-text list — into one combined ranking. Each document gets a score that sums
1 / (k + rank) across the lists it appears in, where k is a smoothing constant fixed at 60.
Because the contribution depends on rank rather than each engine's raw score, RRF needs no
score normalization between the two very different scales (cosine similarity vs ts_rank_cd).
Documents that rank well in both lists rise to the top, so hybrid fusion typically beats either
vector-only or keyword-only retrieval on its own. This is the core of our hybrid search.
