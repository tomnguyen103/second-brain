# ADR-0015 — Local-first runtime; VPS is optional

- **Status:** Accepted
- **Date:** 2026-06-05
- **Deciders:** project owner
- **Context phase:** Post-roadmap runtime reassessment
- **Supersedes:** ADR-0011 as the default runtime/provider decision
- **Relates:** ADR-0012 productionization + data governance, ADR-0014 Kubernetes learning track

## Context

The project originally optimized for a small always-on VPS so the assistant could be available
24/7. In practice, the owner uses the app intermittently. Paying a DigitalOcean droplet to sit
idle conflicts with the cost-conscious goal, even if the monthly amount is small.

The app already has the important engineering artifacts without requiring always-on hosting:
Docker Compose, FastAPI, Postgres + pgvector, Redis, worker jobs, CI eval gates, runbooks,
metrics, RLS, audit, retention, erasure, and Kubernetes learning-track manifests. The VPS path is
therefore useful as a demo or future deployment recipe, but not necessary for daily value.

## Decision

Use **local-first Docker Compose** as the default runtime.

- Run the stack on the owner's machine when needed.
- Stop the stack when not in use.
- Schedule briefings locally only when desired, for example with Windows Task Scheduler or an
  explicit enqueue command.
- Keep `deploy/docker-compose.prod.yml`, `deploy/docker-compose.vps.yml.example`, Caddy config,
  and VPS runbooks as optional deployment artifacts.
- Treat any VPS, managed database, hosted monitoring service, or managed Kubernetes cluster as an
  explicit opt-in cost that requires approval before provisioning.

For remote access to a locally running instance, prefer a free personal VPN/tunnel such as
Tailscale over a permanent public droplet, unless the owner explicitly wants public HTTPS for a
short demo.

## Consequences

- **Good:** default recurring infrastructure cost drops to $0.
- **Good:** the app matches real usage: personal, intermittent, private, and easy to stop.
- **Good:** the portfolio story becomes more honest: the project demonstrates production-grade
  controls without pretending a single-user assistant requires 24/7 paid uptime.
- **Good:** user data stays local by default, except for configured hosted Gemini generation or
  hosted Gemini embeddings.
- **Trade-off:** no always-on web URL, daily briefing, or remote API unless the local machine is
  running or an optional tunnel/cloud deployment is active.
- **Trade-off:** local backups become more important because the database now lives with the local
  runtime by default.
- **Retained:** the previous DigitalOcean/Caddy path remains available for temporary demos or a
  future always-on reversal.

## Alternatives considered

- **Keep the DigitalOcean VPS running.** Simple and already verified, but creates a recurring bill
  for low usage.
- **Move to free platform services.** Vercel/Render/Neon/Supabase-style free tiers can work for
  demos, but they add sleep/cap behavior, privacy changes, and platform-specific constraints. This
  is not simpler than local-first for a personal tool.
- **Oracle Cloud Always Free.** No monthly cost, but capacity/reclamation friction still makes it
  less predictable than local/on-demand for this owner.
- **Managed Kubernetes.** Strong demo value, wrong permanent runtime for a single-user app and a
  known source of surprise bills.
