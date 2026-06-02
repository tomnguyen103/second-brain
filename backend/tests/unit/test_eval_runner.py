"""Eval runner arg handling (ADR-0008). DB-free (returns before touching the DB/model)."""
from app.eval.runner import main


def test_unknown_config_returns_2(capsys):
    rc = main(["--configs", "bogus"])
    assert rc == 2
    assert "unknown config" in capsys.readouterr().err


def test_unknown_among_known_still_rejected():
    assert main(["--configs", "baseline,bogus"]) == 2
