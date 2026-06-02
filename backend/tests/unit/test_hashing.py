from app.ingest.hashing import normalize, content_hash


def test_normalize_collapses_whitespace():
    assert normalize("  a\n\n b\t c ") == "a b c"


def test_hash_is_stable_and_whitespace_insensitive():
    assert content_hash("a b c") == content_hash("  a  b   c ")
    assert len(content_hash("x")) == 64
    assert content_hash("a") != content_hash("b")
