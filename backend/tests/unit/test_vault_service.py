import pytest

from app.vault.service import read_note, require_approved_note, write_note


def test_write_note_rejects_non_markdown(tmp_path):
    with pytest.raises(ValueError):
        write_note(tmp_path, "10 Research/note.txt", "hello")


def test_require_approved_note_checks_frontmatter(tmp_path):
    write_note(
        tmp_path,
        "10 Research/approved.md",
        '---\ntitle: "Approved"\nstatus: approved\ntags: [research]\n---\n# Approved\nSafe text.',
    )
    note = read_note(tmp_path, "10 Research/approved.md")
    require_approved_note(note)

    write_note(tmp_path, "10 Research/draft.md", "---\nstatus: draft\n---\n# Draft\nSafe text.")
    draft = read_note(tmp_path, "10 Research/draft.md")
    with pytest.raises(ValueError):
        require_approved_note(draft)


def test_write_note_rejects_sensitive_content(tmp_path):
    with pytest.raises(ValueError):
        write_note(tmp_path, "10 Research/secret.md", "api_key=verysecretvalue")
