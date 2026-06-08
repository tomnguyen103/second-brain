# Netlify Static Portfolio Demo

This runbook publishes a zero-dollar, always-available portfolio preview of Second Brain as a static Netlify site. It is separate from the normal local-first app: no backend, database, Redis, Gemini key, API token, admin token, or private notes are deployed.

## What The Static Demo Shows

- WattVision web shell, navigation, chat, search, status, sources, feedback, briefing, tasks, research, and admin surfaces.
- Public-safe fixture corpus matching `python -m app.demo.seed_public`.
- Deterministic cited answers for regular RAG and Agentic RAG demo prompts.
- Read-only behavior for capture, ingest, source edits, task creation, research enqueue, eval promotion, deletion, and retention purge.
- Optional browser-side passcode gate for casual access control.

## Important Access Boundary

`NEXT_PUBLIC_DEMO_ACCESS_HASH` is shipped to the browser because this is a static site. It limits casual visitors but is not a security boundary. Only public-safe content belongs in this demo.

## Netlify Site Setup

1. Push this branch to GitHub.
2. In Netlify, choose **Add new site** -> **Import an existing project**.
3. Select the GitHub repository.
4. Use the settings already committed in `netlify.toml`:

```toml
[build]
base = "frontend"
command = "npm ci && npm run build"
publish = "out"
```

5. Add this environment variable in Netlify:

```text
NEXT_PUBLIC_DEMO_ACCESS_HASH=<lowercase sha256 hash of your demo passcode>
```

If you omit `NEXT_PUBLIC_DEMO_ACCESS_HASH`, the passcode gate is disabled and all visitors get immediate access. Only add this variable when you want casual access control for the static demo.

Netlify already receives these from `netlify.toml`:

```text
NEXT_PUBLIC_SECOND_BRAIN_DEMO_MODE=static
NEXT_PUBLIC_AGENTIC_RAG_ENABLED=true
NEXT_TELEMETRY_DISABLED=1
```

Do not add these to Netlify for the static demo:

```text
DATABASE_URL
SECOND_BRAIN_API_TOKEN
SECOND_BRAIN_ADMIN_TOKEN
GEMINI_API_KEY
SECOND_BRAIN_TEST_DATABASE_URL
```

## Generate The Passcode Hash

Run this locally in PowerShell. Replace the example passcode before using it.

```powershell
$passcode = "replace-with-your-demo-passcode"
$bytes = [System.Text.Encoding]::UTF8.GetBytes($passcode)
$hash = [System.Security.Cryptography.SHA256]::HashData($bytes)
($hash | ForEach-Object { $_.ToString("x2") }) -join ""
```

Paste only the resulting hash into Netlify as `NEXT_PUBLIC_DEMO_ACCESS_HASH`.

## Local Verification

From `frontend/`:

```powershell
npm ci
npm run lint
# Verify the normal app build still works before enabling static demo export.
npm run build
$env:NEXT_PUBLIC_SECOND_BRAIN_DEMO_MODE="static"
$env:NEXT_PUBLIC_AGENTIC_RAG_ENABLED="true"
# Build the Netlify static export.
npm run build
```

The static build should create `frontend/out`. Preview it with any static file server, for example:

```powershell
python -m http.server 4173 --directory out
```

Open `http://localhost:4173/chat/` and verify:

- `/chat/` answers the suggested prompts with citations.
- `/search/` returns fixture corpus hits.
- `/sources/` shows one public demo source and seven documents.
- `/status/` reports `static-demo` runtime and no MCP mutations.
- write operations show read-only errors instead of calling a backend.

## Portfolio Link

After Netlify deploys successfully, add the live-demo URL to your personal portfolio site and to `README.md` under a clearly labeled `Live Demo` or `Deployment` section. Keep the repository link immediately adjacent, for example: `Live demo: <Netlify URL> (Repo: <repo URL>)`. Verify the live demo link is reachable after deployment.
