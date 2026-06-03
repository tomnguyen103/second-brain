# Runbook - Export private data to Obsidian, then purge VPS

Use this only after ADR-0015 is accepted and the local vault exists at
`C:\Users\huuth\Documents\SecondBrainVault`.

This runbook is deliberately gated. Do not delete remote/VPS data until keeper notes have been
exported, reviewed, and verified locally.

## 1. Prepare

- Confirm the local vault opens in Obsidian.
- Confirm the folder structure exists:
  - `00 Inbox`
  - `10 Research`
  - `20 Projects`
  - `30 Decisions`
  - `40 Sources`
  - `50 Agent Outputs`
  - `90 Archive`
  - `Templates`
- Decide which data classes are keepers:
  - research notes
  - briefings
  - high-value chat answers
  - source documents worth preserving

## 2. Export

Export data from the current app/VPS using existing admin export endpoints or direct reviewed SQL.
Prefer source-level export first because it matches the current data-ops model.

For each exported item, create Markdown in the vault rather than bulk-copying raw JSON. Suggested
destinations:

- research notes -> `10 Research`
- important project notes -> `20 Projects`
- architecture choices -> `30 Decisions`
- source summaries -> `40 Sources`
- selected agent/chat outputs -> `50 Agent Outputs`

Do not export secrets, API keys, access tokens, raw credentials, or low-value chat transcripts.
Do not use `90 Archive/` as the only destination for keeper notes unless the local index config is
changed, because that folder is excluded from daily vault indexing by default.

## 3. Verify

Before deleting anything:

- Count exported Markdown notes.
- Spot-check note content, titles, tags, and sources.
- Check the current local status with `vault_status`.
- Reindex the vault locally with `reindex_vault`.
- Confirm the approved reindex result has sensible `requested`, `indexed`, `skipped`,
  `removed_stale`, and `excluded` counts.
- Check `vault_status` again and confirm the indexed document count matches expectations.
- Search for representative topics with `search_vault`.
- Confirm the local notes are readable in Obsidian.

Record the verification result in `docs/PROGRESS.md`.

## 4. Purge Remote Personal Data

Only after verification:

- Back up the VPS database.
- Use source-level delete/export endpoints or reviewed SQL to remove private data.
- Keep a sanitized demo corpus for the public app.
- Verify `/search`, `/chat`, and screenshots still work against demo data.

Do not purge automatically from an agent workflow. Destructive remote operations require explicit
human confirmation in the current session.

## 5. Aftercare

- Update `docs/PROGRESS.md` with what was exported and purged.
- Update `docs/implementation-notes.md` with any trade-offs or surprises.
- Keep the VPS as portfolio/demo infrastructure, not private durable memory.
