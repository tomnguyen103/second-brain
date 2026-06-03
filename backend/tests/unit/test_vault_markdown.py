from app.vault.markdown import note_tags, render_note, split_frontmatter


def test_split_frontmatter_and_tags():
    content = """---
title: "My Note"
tags: [research, ai]
---
# Heading

Body #agent/security
"""
    metadata, body = split_frontmatter(content)
    assert metadata["title"] == "My Note"
    assert metadata["tags"] == ["research", "ai"]
    assert "Body" in body
    assert note_tags(content, metadata) == ["agent/security", "ai", "research"]


def test_split_frontmatter_handles_crlf():
    content = "---\r\ntitle: Windows Note\r\ntags: [vault]\r\n---\r\n# Heading\r\n\r\nBody"

    metadata, body = split_frontmatter(content)

    assert metadata == {"title": "Windows Note", "tags": ["vault"]}
    assert body == "# Heading\n\nBody"


def test_render_note_labels_derived_sources():
    note = render_note(
        title="NotebookLM Session",
        body="Distilled notes.",
        kind="notebooklm-capture",
        tags=["notebooklm", "derived"],
        sources=["paper.pdf"],
    )
    assert "kind: notebooklm-capture" in note
    assert "# NotebookLM Session" in note
    assert "- paper.pdf" in note


def test_render_note_quotes_frontmatter_values():
    note = render_note(
        title='Notebook "Quoted"\nSession',
        body="Distilled notes.",
        kind="research",
        tags=['ai "notes"', "local"],
    )

    assert 'title: "Notebook \\"Quoted\\" Session"' in note
    assert 'tags: ["ai \\"notes\\"", "local"]' in note
