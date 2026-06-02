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
