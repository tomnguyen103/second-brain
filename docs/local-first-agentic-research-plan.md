# Local-first Agentic Research Plan

This plan defines how manual research, Obsidian, and Second Brain work together without making
NotebookLM an automated integration.

## Operating Model

Second Brain has two research paths:

- **App-owned research:** the MCP `research_topic` tool uses the Gemini API, writes a research note,
  and ingests it through the app. This is automated inside the app boundary.
- **NotebookLM-assisted research:** the owner uses NotebookLM manually, then saves only reviewed
  Markdown into Obsidian before reindexing it through Second Brain.

NotebookLM is a study tool, not a pipeline dependency.

## Vault Roles

Use `C:\Users\huuth\Documents\SecondBrainVault` as the local working memory surface.

| Folder | Role |
|---|---|
| `10 Research` | Research briefs, daily prompt, reviewed topic notes |
| `40 Sources` | Source digests and source-specific notes |
| `50 Agent Outputs` | Reviewed outputs from Second Brain or other agents |
| `30 Decisions` | Durable decisions and ADR-like notes |
| `90 Archive` | Old notes that should not be active working context |
| `Templates` | Obsidian templates for repeatable capture |

## Note Types

Every research note should carry frontmatter with:

- `title`
- `kind`
- `status`
- `created`
- `derived`
- `source_tool`
- `tags`

Default kinds:

- `research-brief`: the question, decision context, source plan, and approved keeper summary.
- `notebooklm-session`: selected output from a manual NotebookLM run.
- `source-digest`: one source summarized with claims, evidence, caveats, and links.
- `workflow-prompt`: reusable operating prompts such as the daily research prompt.

## Daily Loop

1. Ask the question in a `Research Brief`.
2. Search Second Brain before opening NotebookLM.
3. Decide whether NotebookLM is needed.
4. If needed, use NotebookLM manually with focused sources and prompts.
5. Paste only useful, source-aware output into Obsidian templates.
6. Save approved Markdown in the vault.
7. Reindex the approved note through Second Brain `/ingest`.
8. Search verify with the original question and one important term.

## Quality Rules

- Do not save raw NotebookLM transcripts by default.
- Do not ingest secrets, credentials, private contact details, or payment details.
- Keep short quotes source-labeled.
- Prefer claims with source context over broad summaries.
- Mark NotebookLM-derived notes with `derived: true` and `source_tool: notebooklm`.
- Keep `status: draft` until the note is approved for ingest.

## Future Work

The next useful improvement would be a small local ingest helper or UI affordance for approved
vault notes. That would automate reindexing, not NotebookLM. It should still preserve the human
approval gate.
