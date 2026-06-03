# Windows Setup Guide - Second Brain With Codex MCP

This guide is for using Second Brain locally on Windows.

The simple idea:

```text
Obsidian = your real memory
Codex / Claude = agent interface
Second Brain MCP = safe tools
Postgres = local search index
VPS = demo only
```

You do **not** need to post to the FastAPI app for the normal Obsidian workflow. Use MCP tools
from Codex or Claude.

## One-Time Initial Setup

Do this once on your machine.

### 1. Open The Obsidian Vault

Open Obsidian and choose this vault:

```text
C:\Users\huuth\Documents\SecondBrainVault
```

You should see:

```text
00 Inbox
10 Research
20 Projects
30 Decisions
40 Sources
50 Agent Outputs
90 Archive
Templates
```

This vault is your real long-term memory.

### 2. Start The Local Database

Open PowerShell:

```powershell
cd C:\Users\huuth\Desktop\second-brain
docker compose up -d db
```

Check that it is running:

```powershell
docker ps --filter name=second_brain_db
```

### 3. Prepare The Backend

In PowerShell:

```powershell
cd C:\Users\huuth\Desktop\second-brain\backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

If `.venv` does not exist:

```powershell
cd C:\Users\huuth\Desktop\second-brain\backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
alembic upgrade head
```

### 4. Connect Codex To The MCP Server

Open:

```text
C:\Users\huuth\.codex\config.toml
```

Add this block near the other `[mcp_servers...]` entries:

```toml
[mcp_servers.second_brain_local]
command = 'C:\Users\huuth\Desktop\second-brain\backend\.venv\Scripts\python.exe'
args = ['-m', 'app.mcp_server']
startup_timeout_sec = 120

[mcp_servers.second_brain_local.env]
PYTHONPATH = 'C:\Users\huuth\Desktop\second-brain\backend'
SECOND_BRAIN_DATABASE_URL = 'postgresql+psycopg://second_brain:second_brain@localhost:5433/second_brain'
SECOND_BRAIN_VAULT_PATH = 'C:\Users\huuth\Documents\SecondBrainVault'
SECOND_BRAIN_LLM_PROVIDER = 'fake'
SECOND_BRAIN_MCP_APPROVAL_TOKEN = '<choose-a-local-approval-token>'
# Optional JSON lists. Defaults exclude .obsidian, Templates, and 90 Archive.
# SECOND_BRAIN_VAULT_INDEX_EXCLUDE_DIRS = '[".obsidian", "Templates", "90 Archive"]'
# SECOND_BRAIN_VAULT_INDEX_INCLUDE_DIRS = '[]'
```

Restart Codex completely.

### 5. Check The MCP Tools

In a new Codex thread, ask:

```md
Use the `second_brain_local` MCP server. List the available Second Brain MCP tools.
Do not write anything yet.
```

You should see tools like:

```text
search_vault
read_note
propose_note_write
create_research_note
capture_notebooklm_session
reindex_vault
vault_status
pending_approvals
approve_tool_call
```

### 6. Create A Smoke-Test Note

Ask Codex:

```md
Use `propose_note_write` to create this note:

path: 00 Inbox/Codex MCP Smoke Test.md
mode: overwrite
content:
# Codex MCP Smoke Test

This note was created through the local Second Brain MCP server.

Do not approve it yet. Show me the approval id first.
```

Then approve:

```md
After I confirm the pending id, call `approve_tool_call` for that id.
If a token is configured, I will provide it out-of-band; do not put the real token in this chat.
```

Open Obsidian and confirm this file exists:

```text
00 Inbox/Codex MCP Smoke Test.md
```

### 7. Index And Search

Ask Codex:

```md
Use `vault_status` and show me the vault/index counts.
```

Then ask:

```md
Use `reindex_vault` for all vault notes. Show me the approval id first.
```

Approve it:

```md
After I confirm the pending id, call `approve_tool_call` for that id.
Use the approval token only through a trusted local/manual step, not in model-visible chat.
```

Then ask:

```md
Use `search_vault` for: Codex MCP Smoke Test. Show me the approval id first.
```

Approve that too. Codex should find the smoke-test note.

## Daily Setup

Do this when you want to use Second Brain.

### 1. Open Obsidian

Open:

```text
C:\Users\huuth\Documents\SecondBrainVault
```

### 2. Start The Local Database

PowerShell:

```powershell
cd C:\Users\huuth\Desktop\second-brain
docker compose up -d db
```

### 3. Open Codex In The Project Folder

Use Codex from:

```text
C:\Users\huuth\Desktop\second-brain
```

That gives Codex the project docs, code, and MCP context.

### 4. Use A Startup Prompt

Paste this into Codex:

```md
Read `AGENTS.md`, `docs/PROGRESS.md`, `docs/local-first-agentic-research-plan.md`,
and `docs/adr/0015-local-first-obsidian-memory.md`.

Use the `second_brain_local` MCP server when working with my Obsidian vault.
Do not write to the vault until I approve.
Do not use the VPS for private memory.
```

### 5. Reindex When Needed

Reindex after you add or edit notes that you want searchable:

```md
Use `vault_status` and show me the vault/index counts.
```

```md
Use `reindex_vault` for all vault notes. Show me the approval id first.
```

Then approve with:

```md
Call `approve_tool_call` only after I confirm the pending id.
Keep any configured approval token out of the model-visible transcript.
```

## Where To Use It

### Best Place: Codex In The Project Folder

Use this for implementation, docs, MCP work, and maintaining the project:

```text
C:\Users\huuth\Desktop\second-brain
```

This is the best place when you want Codex to understand the codebase.

### Good Place: Codex Regular Chat

Use regular Codex chat for personal research workflow:

```text
question -> NotebookLM planning -> pasted output -> Obsidian note -> reindex
```

Make sure the `second_brain_local` MCP server is available.

### Good Place: Claude Desktop / Claude Code

Claude can also use the same MCP server if you add an equivalent MCP config:

```text
command: C:\Users\huuth\Desktop\second-brain\backend\.venv\Scripts\python.exe
args: -m app.mcp_server
env:
  PYTHONPATH=C:\Users\huuth\Desktop\second-brain\backend
  SECOND_BRAIN_DATABASE_URL=postgresql+psycopg://second_brain:second_brain@localhost:5433/second_brain
  SECOND_BRAIN_VAULT_PATH=C:\Users\huuth\Documents\SecondBrainVault
  SECOND_BRAIN_LLM_PROVIDER=fake
  SECOND_BRAIN_MCP_APPROVAL_TOKEN=<choose-a-local-approval-token>
```

Use Claude for long research conversations or writing polished notes. Use Codex when code or repo
changes are involved.

### Not Recommended: VPS For Private Memory

The VPS is now for demo and portfolio only. Do not use it as the place where private research lives.

## Important Things To Remember

### Obsidian Is The Source Of Truth

If something matters long term, it should become a Markdown note in:

```text
C:\Users\huuth\Documents\SecondBrainVault
```

Postgres is only a search index. It can be rebuilt.

### NotebookLM Is Manual

Use NotebookLM for deep research by hand.

Good workflow:

```text
Codex prepares research questions
you use NotebookLM manually
you paste useful output back
Codex creates an Obsidian note
you approve
Codex reindexes
```

### Do Not Save Everything

Save:

- reusable conclusions
- decisions
- good source summaries
- NotebookLM synthesis worth keeping
- project knowledge you expect to search later

Do not save:

- raw transcripts
- low-value chat
- duplicate summaries
- secrets or API keys
- private data you do not want future agents reading

### Approval Is Required

Most vault actions return:

```text
approval_required
```

Approve with:

```text
Use `approve_tool_call` after personally confirming the pending id.
Keep the real approval token out of model-visible chat; enter it only in a trusted local/manual step.
```

This is annoying on purpose. It protects your vault while the workflow is new.

### Use Vault-Relative Paths

Correct:

```text
10 Research/My Note.md
```

Wrong:

```text
C:\Users\huuth\Documents\SecondBrainVault\10 Research\My Note.md
```

The MCP server blocks full paths and path traversal for safety.

### Indexing Skips Noisy Folders

Full-vault reindexing excludes these folders by default:

```text
.obsidian
Templates
90 Archive
```

Use `vault_status` before and after reindexing to see the vault path, indexed source, indexed
document count, pending approvals count, and eligible/excluded Markdown counts. An approved
`reindex_vault` result reports `requested`, `indexed`, `skipped`, `removed_stale`, and `excluded`.

If you want archived notes searchable for a specific workflow, change the local MCP environment
variables:

```toml
SECOND_BRAIN_VAULT_INDEX_EXCLUDE_DIRS = '[".obsidian", "Templates"]'
```

### No API Key Needed At First

The Codex MCP config starts with:

```toml
SECOND_BRAIN_LLM_PROVIDER = 'fake'
```

That means no Gemini API key is needed.

Later, for real Gemini:

```toml
SECOND_BRAIN_LLM_PROVIDER = 'gemini'
SECOND_BRAIN_GEMINI_API_KEY = '<your Gemini API key>'
```

### You Usually Do Not Need HTTP APIs

For the local-first workflow, use MCP tools.

The FastAPI endpoints are optional and mostly for the app/demo:

- `POST /ingest`
- `POST /chat`
- `GET /search`

### Do Not Purge VPS Data Casually

Before deleting anything remote:

1. Export keeper data.
2. Convert it to Markdown.
3. Verify it in Obsidian.
4. Reindex and search locally.
5. Back up the VPS DB.
6. Then purge only with explicit approval.

Follow:

```text
docs/runbooks/local-first-export-purge.md
```

## Simple Daily Prompt

Use this when starting a research session:

```md
I want to research: <topic/question>

Use my local-first Second Brain workflow:
1. help me decide if this needs NotebookLM
2. prepare NotebookLM questions and source checklist
3. after I paste NotebookLM output, turn only the useful parts into an Obsidian note
4. use Second Brain MCP tools to save only after I approve
5. reindex the saved note
6. verify it with search_vault

Do not save raw transcripts. Do not use the VPS for private memory.
```

## Quick Troubleshooting

### Codex Does Not See The Tools

- Restart Codex.
- Check `C:\Users\huuth\.codex\config.toml`.
- Make sure the `[mcp_servers.second_brain_local]` block exists.

### Database Error

Run:

```powershell
cd C:\Users\huuth\Desktop\second-brain
docker compose up -d db
```

Then:

```powershell
cd C:\Users\huuth\Desktop\second-brain\backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

### Search Finds Nothing

Run and approve:

```text
vault_status
reindex_vault
```

Then search again.
