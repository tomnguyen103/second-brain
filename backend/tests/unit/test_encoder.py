from app.embeddings import encoder


def test_encode_shape_and_norm(monkeypatch):
    class _Stub:
        def encode(self, texts, normalize_embeddings=True):
            return [[0.6, 0.8] + [0.0] * 382 for _ in texts]
    monkeypatch.setattr(encoder, "_model", lambda: _Stub())
    out = encoder.Embedder().encode(["a", "b"])
    assert len(out) == 2 and len(out[0]) == 384
    assert abs((out[0][0] ** 2 + out[0][1] ** 2) ** 0.5 - 1.0) < 1e-6
