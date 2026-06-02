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
