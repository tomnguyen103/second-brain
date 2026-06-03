# Runbook - Local-first export and future purge prep

Status: prep-only. Do not purge in this session.

This runbook prepares a safe path for reviewing keeper data from the local Second Brain database,
moving approved Markdown into Obsidian, reindexing it, and only later considering a VPS/app data
purge after a fresh backup and explicit approval.

## Hard Rules

- Do not delete data while running this prep workflow.
- Do not run VPS commands or call the live VPS API unless the owner explicitly approves it in the
  same session.
- Treat `DELETE /data/sources/{id}` and `POST /admin/retention/purge` as future purge steps only.
- Export to a temporary local folder first. Obsidian remains the approval surface.
- Back up Postgres before any future purge, even if the keeper export looks good.

## Current Export Options

Local options:

- Direct local DB read through `SECOND_BRAIN_DATABASE_URL`, defaulting to
  `localhost:5433/second_brain`.
- Local-only Markdown dry-run:
  `python -m app.dataops.export_markdown`.
- Existing app JSON export:
  `GET /data/export?source_id=<id>` with the admin token. This is read-only for user data, but it
  commits an `audit_log` export row, so it is not a pure dry-run.
- Existing content APIs:
  `GET /briefing`, `GET /briefing/history`, `GET /conversations`,
  `GET /conversations/{id}`, and `GET /search`.
- Existing reindex API:
  `POST /ingest` with `source.type = "notes_folder"` for approved Obsidian notes.

VPS options, approval required before use:

- HTTPS app API at `https://YOUR_VPS_IP.sslip.io/api`.
- Docker Compose access on the droplet using project name `second-brain`.
- Logical backup path in `docs/runbooks/backup-restore.md`.
- Admin JSON export, delete, and retention purge endpoints behind the bearer token.

## Keeper Checklist

Use this checklist while reviewing the temp export folder.

Research notes:

- [ ] The note contains a durable claim, decision, or reusable explanation.
- [ ] The topic is clear from title and frontmatter.
- [ ] The content is not just a raw transcript or low-signal brainstorm.
- [ ] Claims that came from external sources keep enough context to trace them.
- [ ] No secrets, credentials, private contact details, or payment details are present.
- [ ] Destination: `C:\Users\huuth\Documents\SecondBrainVault\10 Research`.

Important briefings:

- [ ] The briefing changed a decision, reminded you of something worth keeping, or summarizes a
  period you want preserved.
- [ ] The generated summary is still useful without the original app UI.
- [ ] The document list is preserved when it matters.
- [ ] Empty "nothing new" briefings are skipped unless there is a reason to archive them.
- [ ] Destination: `C:\Users\huuth\Documents\SecondBrainVault\50 Agent Outputs`.

Important chat answers:

- [ ] The answer is one you would search for later.
- [ ] The question is included with the answer.
- [ ] Citations or source snippets are present when the answer depends on retrieved context.
- [ ] Positive feedback or manual review justifies keeping it.
- [ ] Destination: `C:\Users\huuth\Documents\SecondBrainVault\50 Agent Outputs`.

Source documents worth preserving:

- [ ] The source is a canonical document, PDF, bookmark, manual note, or vault note worth keeping
  outside the app DB.
- [ ] The exported Markdown includes provenance: source name, type, URI if available, and document id.
- [ ] If the body was reconstructed from chunks, confirm the text is complete enough for reuse.
- [ ] If the export is truncated, review the original source before approving.
- [ ] Destination: `C:\Users\huuth\Documents\SecondBrainVault\40 Sources`.

## Markdown Export Formats

All keeper files use YAML frontmatter followed by review checklist sections. The initial status is
always `review`; change it to `approved` only after reindex and search verification.

Research note:

```markdown
---
title: "Topic title"
kind: "research-note"
status: "review"
created: "2026-06-03T00:00:00+00:00"
derived: true
source_tool: "second-brain"
second_brain_source_id: 1
second_brain_document_id: 2
content_source: "raw_text"
truncated: false
tags:
  - "second-brain-export"
  - "research"
---

# Topic title

## Keeper Review
...

## Provenance
...

## Research Note
...
```

Briefing:

```markdown
---
title: "Second Brain briefing 2026-06-03 07:00 UTC"
kind: "briefing"
status: "review"
created: "2026-06-03T07:00:00+00:00"
derived: true
source_tool: "second-brain"
second_brain_briefing_id: 1
period_start: "2026-06-02T07:00:00+00:00"
period_end: "2026-06-03T07:00:00+00:00"
document_count: 4
model: "gemini-2.5-flash"
tags:
  - "second-brain-export"
  - "briefing"
---

# Briefing 2026-06-03

## Summary
...

## Stored Briefing
...
```

Chat answer:

```markdown
---
title: "Chat answer 42"
kind: "chat-answer"
status: "review"
created: "2026-06-03T12:00:00+00:00"
derived: true
source_tool: "second-brain"
second_brain_conversation_id: 12
second_brain_message_id: 42
important_signal: "positive-feedback"
model: "gemini-2.5-flash"
latency_ms: 1400
tags:
  - "second-brain-export"
  - "chat-answer"
---

# Chat Answer 42

## Question
...

## Answer
...

## Citations
...

## Feedback
...
```

Source document:

```markdown
---
title: "Source title"
kind: "source-document"
status: "review"
created: "2026-06-03T12:00:00+00:00"
derived: false
source_tool: "second-brain"
second_brain_source_id: 8
second_brain_document_id: 21
original_source_type: "pdf_upload"
content_source: "raw_text"
truncated: false
tags:
  - "second-brain-export"
  - "source-document"
---

# Source title

## Provenance
...

## Content
...
```

## Local Dry-run Export

From the repo root, start only the local DB if needed:

```powershell
docker compose up -d db
```

Run migrations if the local DB is fresh:

```powershell
Set-Location C:\Users\huuth\Desktop\second-brain\backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

Export all keeper candidates to a new temp folder:

```powershell
Set-Location C:\Users\huuth\Desktop\second-brain\backend
.\.venv\Scripts\Activate.ps1

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$exportDir = Join-Path $env:TEMP "second-brain-keeper-export-$stamp"
python -m app.dataops.export_markdown --confirm-local-export local-only --output-dir $exportDir
```

The exporter refuses non-local DB hosts. It writes local files only and rolls back a read-only DB
transaction before exit.

Optional narrower exports:

```powershell
$exportDir = Join-Path $env:TEMP "second-brain-keeper-export-briefings-$stamp"
python -m app.dataops.export_markdown --confirm-local-export local-only --kinds briefings --output-dir $exportDir

$exportDir = Join-Path $env:TEMP "second-brain-keeper-export-chat-$stamp"
python -m app.dataops.export_markdown --confirm-local-export local-only --kinds chat-answers --chat-mode recent-cited --output-dir $exportDir

$exportDir = Join-Path $env:TEMP "second-brain-keeper-export-sources-$stamp"
python -m app.dataops.export_markdown --confirm-local-export local-only --kinds source-documents --source-documents-limit 25 --output-dir $exportDir
```

Local dev databases may include eval corpus rows, smoke-test seeds, or Obsidian templates. Treat
those as review candidates, not automatic keepers; skip them unless they are intentionally useful.

## Verification Steps

Count exported files:

```powershell
Get-ChildItem -LiteralPath $exportDir -Recurse -Filter *.md | Measure-Object
Get-ChildItem -LiteralPath $exportDir -Directory | ForEach-Object {
  [pscustomobject]@{
    Kind = $_.Name
    Count = (Get-ChildItem -LiteralPath $_.FullName -Filter *.md | Measure-Object).Count
  }
}
```

Spot-check content:

```powershell
Get-Content -Raw -LiteralPath (Get-ChildItem -LiteralPath $exportDir -Recurse -Filter *.md | Select-Object -First 1).FullName
```

Move approved notes into Obsidian:

```powershell
$vault = "C:\Users\huuth\Documents\SecondBrainVault"
# Example after manual approval:
# Move-Item -LiteralPath "$exportDir\research-notes\approved-note.md" -Destination "$vault\10 Research\approved-note.md"
```

Reindex one approved note:

The note must include Markdown frontmatter with `status: approved`; `notes_folder` ingest rejects
draft or unmarked Markdown.

```powershell
$apiBase = "http://localhost:8000"
$notePath = "C:\Users\huuth\Documents\SecondBrainVault\10 Research\My Approved Note.md"
$content = Get-Content -Raw -LiteralPath $notePath
$title = [System.IO.Path]::GetFileNameWithoutExtension($notePath)

$body = @{
  source = @{
    type = "notes_folder"
    name = "SecondBrainVault"
    uri = $notePath
  }
  documents = @(
    @{
      title = $title
      content = $content
      tags = @("obsidian", "keeper")
    }
  )
} | ConvertTo-Json -Depth 8

Invoke-RestMethod -Uri "$apiBase/ingest" -Method Post -ContentType "application/json" -Body $body
```

Search verify:

```powershell
$query = [uri]::EscapeDataString("an important term from the approved note")
Invoke-RestMethod -Uri "$apiBase/search?q=$query&top_k=5"
```

Back up DB before any future purge:

```powershell
# Local backup example from repo root:
docker compose exec -T db pg_dump -U second_brain -d second_brain -Fc > "$env:TEMP\second-brain-pre-purge.dump"
```

For VPS backup commands, use `docs/runbooks/backup-restore.md` only after explicit approval to
touch the VPS.

## Future Purge Gate

Stop here for the prep session.

Before any later purge:

- [ ] Confirm all keeper notes are approved in Obsidian.
- [ ] Confirm approved notes were reindexed through `/ingest`.
- [ ] Confirm search returns the approved notes.
- [ ] Take and verify a fresh Postgres backup.
- [ ] Decide exactly what to purge: source delete, retention raw-text purge, or no purge.
- [ ] Get explicit owner approval in that session.

No purge command belongs in the prep-only workflow.

The live endpoints now add their own guardrails: retention purge previews by default and requires
`dry_run=false&confirm=purge raw_text` to mutate; source delete requires `confirm_source_name`
matching the current source name.
