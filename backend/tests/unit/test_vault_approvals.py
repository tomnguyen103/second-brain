import pytest

from app.vault import approvals


@pytest.fixture(autouse=True)
def clear_pending():
    approvals._PENDING.clear()
    yield
    approvals._PENDING.clear()


def test_approval_is_single_use():
    request = approvals.request_approval("read_note", {"path": "a.md"}, "read")
    approval_id = request["approval"]["id"]
    assert "args" not in request["approval"]
    approval = approvals.pop_approval(approval_id)
    assert approval.tool == "read_note"
    with pytest.raises(ValueError):
        approvals.pop_approval(approval_id)


def test_pending_approvals_hide_raw_args():
    request = approvals.request_approval(
        "propose_note_write",
        {"path": "a.md", "content": "SECRET_VALUE"},
        "write",
        {"path": "a.md", "content": {"chars": 12, "hash": "abc"}},
    )

    pending = approvals.list_pending()

    assert pending == [request["approval"]]
    assert "args" not in pending[0]
    assert "SECRET_VALUE" not in str(pending)
