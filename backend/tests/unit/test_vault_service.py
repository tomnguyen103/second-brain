import pytest

from app.vault.service import list_markdown_files, read_note, require_approved_note, write_note


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


def test_list_markdown_files_includes_uppercase_extension(tmp_path):
    write_note(tmp_path, "10 Research/NOTE.MD", "---\nstatus: approved\n---\n# Note\nSafe text.")
    files = list_markdown_files(tmp_path, ["10 Research"], [])
    assert [p.name for p in files] == ["NOTE.MD"]


def test_append_preserves_leading_whitespace(tmp_path):
    write_note(tmp_path, "10 Research/list.md", "# List\n", mode="create")
    write_note(tmp_path, "10 Research/list.md", "  - indented\n", mode="append")
    content = (tmp_path / "10 Research" / "list.md").read_text(encoding="utf-8")
    assert "\n\n  - indented\n" in content
