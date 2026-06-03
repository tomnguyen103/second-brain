# NotebookLM to Obsidian Workflow

NotebookLM is the manual deep-research room. Obsidian is the durable private memory.
Agents help plan, clean, structure, save, and index notes, but they do not automate NotebookLM
or decide what is worth keeping without user approval.

## Workflow

1. Create a `Research Brief` before opening NotebookLM.
2. Manually collect sources and study them in NotebookLM.
3. Paste useful NotebookLM output back to the agent.
4. Agent converts the useful output into a `NotebookLM Session`, `Source Digest`, or durable
   research note.
5. User reviews the proposed note and approves the MCP write.
6. Agent saves Markdown into the local vault.
7. Agent checks `vault_status`, reindexes the saved note into local Postgres, and checks status again.
8. Agent verifies searchability with `search_vault` and readability with `read_note`.

## Templates

The vault templates live in:

- `C:\Users\huuth\Documents\SecondBrainVault\Templates\Research Brief.md`
- `C:\Users\huuth\Documents\SecondBrainVault\Templates\NotebookLM Session.md`
- `C:\Users\huuth\Documents\SecondBrainVault\Templates\Source Digest.md`

Use `Research Brief` before research, `NotebookLM Session` for a curated capture of one
NotebookLM study session, and `Source Digest` when one source deserves its own durable summary.
The `Templates/` folder is excluded from vault indexing by default, so these template bodies do not
pollute daily search.

## Save Rules

Save:

- A conclusion you expect to reuse.
- A decision, trade-off, or architecture implication.
- A source summary that would be painful to reconstruct.
- A high-signal quote or fact with clear provenance.
- A research question, answer, or open thread that affects a project.
- A synthesis that links multiple sources.

Do not save:

- Raw NotebookLM dumps with no curation.
- Full chat transcripts unless they contain a durable answer.
- Secrets, API keys, tokens, credentials, private payment/contact details, or hidden reasoning.
- Low-confidence claims without source context.
- Duplicate summaries already captured elsewhere.
- Temporary prompts, tool logs, or agent scratch work.
- Content meant only for the VPS demo corpus unless it is sanitized first.

If unsure, save a short `00 Inbox` note with `status: needs-review` rather than a polished
research note.

## Frontmatter Conventions

Required fields for NotebookLM-derived notes:

```yaml
title: "Human-readable title"
kind: notebooklm-session | source-digest | research-brief | research
status: draft | reviewed | keeper | archived
created: YYYY-MM-DD
derived: true
source_tool: notebooklm
tags: ["notebooklm", "derived"]
```

Recommended fields:

```yaml
project: "Second Brain"
research_question: "The question this note answers"
notebooklm_project: "NotebookLM project or notebook name"
sources_count: 0
source_types: ["pdf", "web", "doc", "note"]
confidence: low | medium | high
reviewed_by: "human"
reviewed_at: YYYY-MM-DD
```

Tag conventions:

- `notebooklm`: output came from manual NotebookLM study.
- `derived`: the note is synthesized from sources, not a primary source.
- `research/brief`: research planning note.
- `research/session`: curated NotebookLM session capture.
- `source/digest`: one-source summary.
- `project/<name>`: project link, for example `project/second-brain`.
- `topic/<name>`: stable topic, for example `topic/rag`.
- `status/needs-review`: useful but not yet keeper-quality.

## Safe MCP Workflow for capture_notebooklm_session

1. User pastes selected NotebookLM output and source list into the agent.
2. Agent removes obvious clutter and asks only if the destination or sensitivity is unclear.
3. Agent checks the proposed note for:
   - no secrets, keys, tokens, credentials, or private payment/contact details
   - source-aware claims
   - no raw hidden reasoning
   - clear `derived` labeling
4. Agent calls `capture_notebooklm_session(title, body, sources)`.
5. Tool returns `approval_required` with a compact summary. Raw write body stays process-local.
6. User reviews the pending approval with `pending_approvals`.
7. User approves with `approve_tool_call`. If configured, provide
   `SECOND_BRAIN_MCP_APPROVAL_TOKEN`.
8. Agent records the returned `note.path`.
9. Agent calls `vault_status` to show current vault/index counts.
10. Agent calls `reindex_vault(paths=[note.path])` and gets user approval.
11. Agent confirms the approved result reports the expected `requested`, `indexed`, `skipped`,
    `removed_stale`, and `excluded` counts.
12. Agent verifies with `search_vault` using one or two representative queries.
13. Agent optionally calls `read_note(note.path)` to confirm the saved note is readable.

Never use this workflow to export or purge VPS data. The export/purge workflow remains a separate
explicit runbook with current-session approval.
