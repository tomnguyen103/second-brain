# NotebookLM to Obsidian Workflow

Use this when a question may need deep source work. The goal is a clean, searchable keeper note,
not a transcript archive.

## The Normal Workflow

1. **Ask question**
   - Create a note from `Templates/Research Brief.md`.
   - Write the question and the decision it supports.

2. **Decide if NotebookLM is needed**
   - Search Second Brain first.
   - Use NotebookLM only for long-context source reading, source comparison, or synthesis across
     multiple documents.

3. **Use NotebookLM manually**
   - Load only relevant sources.
   - Ask focused questions.
   - Pull out useful claims, caveats, contradictions, and short source-labeled evidence.
   - Do not automate NotebookLM.

4. **Paste useful output**
   - Use `NotebookLM Session.md` for a reviewed session summary.
   - Use `Source Digest.md` for an important source.
   - Do not save raw transcripts by default.

5. **Save approved Markdown**
   - Move the durable summary into the `Approved Markdown To Ingest` section or a clean keeper note.
   - Keep source context and provenance.
   - Leave the note as `status: draft` until it is ready.

6. **Reindex**
   - Ingest the approved Markdown through Second Brain `/ingest`.
   - Use `source.type = "notes_folder"` for vault notes.

7. **Search verify**
   - Search for the original question.
   - Search for one important term from the note.
   - Confirm the saved note appears in the top results, then set `status: approved`.

## Reindex With PowerShell

Set `$apiBase` to the live API path or local dev API:

```powershell
$apiBase = "https://YOUR_VPS_IP.sslip.io/api"
# or, for local dev:
# $apiBase = "http://localhost:8000"
```

Ingest one approved vault note:

```powershell
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
      tags = @("obsidian", "research")
    }
  )
} | ConvertTo-Json -Depth 8

Invoke-RestMethod -Uri "$apiBase/ingest" -Method Post -ContentType "application/json" -Body $body
```

Verify search:

```powershell
$query = [uri]::EscapeDataString("your original research question")
Invoke-RestMethod -Uri "$apiBase/search?q=$query&top_k=5"
```

## What Not To Save

- Raw NotebookLM chats, audio transcripts, or long copy-paste dumps by default.
- Claims with no source context.
- Secrets, API keys, credentials, private contact details, or payment details.
- Temporary phrasing that will not be useful in search later.

## Templates

The Obsidian Templates plugin is configured to use:

`C:\Users\huuth\Documents\SecondBrainVault\Templates`

Use:

- `Research Brief.md` to start the question.
- `NotebookLM Session.md` to capture reviewed NotebookLM output.
- `Source Digest.md` to preserve one important source.
