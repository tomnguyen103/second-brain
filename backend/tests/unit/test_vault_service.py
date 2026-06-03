import pytest

from app.vault.service import create_research_note, read_note, write_note


def test_write_note_requires_markdown(tmp_path):
    with pytest.raises(ValueError):
        write_note(str(tmp_path), "bad.txt", "content")


def test_create_research_note_writes_markdown(tmp_path):
    note = create_research_note(
        str(tmp_path),
        topic="Agent Security",
        body="Keep durable memory local.",
        sources=["manual NotebookLM synthesis"],
    )
    assert note.path == "10 Research/Agent-Security.md"
    assert note.title == "Agent Security"
    assert "research" in note.tags
    assert "## Synthesis" in note.content
    reread = read_note(str(tmp_path), note.path)
    assert reread.content_hash == note.content_hash


def test_capture_notebooklm_session_uses_capture_template(tmp_path):
    from app.vault.service import capture_notebooklm_session

    note = capture_notebooklm_session(
        str(tmp_path),
        title="NotebookLM Session",
        body="Distilled notes.",
        sources=["paper.pdf"],
    )

    assert note.path == "50 Agent Outputs/NotebookLM-Session.md"
    assert "notebooklm" in note.tags
    assert "derived" in note.tags
    assert "## NotebookLM Capture" in note.content
    assert "- paper.pdf" in note.content


def test_write_note_create_refuses_existing(tmp_path):
    write_note(str(tmp_path), "00 Inbox/a.md", "# A")
    with pytest.raises(FileExistsError):
        write_note(str(tmp_path), "00 Inbox/a.md", "# B")
