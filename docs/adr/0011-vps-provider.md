# ADR-0011 — VPS provider for the always-on runtime

> **Superseded 2026-06-05 by ADR-0015.** Local-first Docker Compose is now the default runtime;
> this VPS provider decision is retained only as historical context and an optional cloud recipe.

- **Status:** Superseded by ADR-0015
- **Date:** 2026-06-02
- **Deciders:** project owner (low cost is the stated priority)
- **Context phase:** Phase 6 (productionize on a VPS)

> **Update 2026-06-02 — supersedes the region & fallback below.** The owner is in the **USA**,
> not SEA — the "SEA (Vietnam)" premise in Context #2 and the Singapore region choice are
> incorrect. **Corrected:** Oracle Cloud Always Free, home region **US Central (Chicago,
> `us-chicago-1`)** ($0, up to 4 ARM OCPU / 24 GB). Paid fallback flips to **Hetzner US**
> (Ashburn VA / Hillsboro OR, ~$5/mo, x86, no ARM-capacity lottery) — Hetzner was dismissed
> below *only* for Vietnam latency, which no longer applies. The RAM-constraint analysis,
> multi-arch note, and $0-baseline rationale all still stand.

## Context

The whole stack runs as one Docker Compose project on a single always-on box (AGENTS.md).
We need to pick the provider. **Low cost is the priority.** Two facts shape the choice:

1. **RAM is the binding constraint, not CPU.** The box runs Postgres+pgvector, Redis, the
   FastAPI API, the local MiniLM/torch embedder (RAM-hungry on ingest), MLflow, Prometheus,
   and Grafana. The LLM is offloaded to the Gemini free tier, so there is **no GPU need** and
   CPU is light; 4 GB works with care, **8 GB is comfortable**.
2. **The owner is in SEA (Vietnam).** It's a daily-use chat UI, so latency from the box to the
   user matters — an Asia/Singapore datacenter is a real tiebreaker.

2026 context: a global DDR5 shortage pushed RAM-heavy plan prices up (Hetzner +20–30%, Netcup
too), which makes the $0 and locked-in-annual options relatively more attractive.

## Decision

**Primary: Oracle Cloud Always Free (Singapore region).** $0 forever, 4 ARM (Ampere A1) OCPU /
24 GB RAM / 200 GB, and an Asia datacenter close to the user — it wins on both stated
priorities. The stack's 24/7 Postgres + Prometheus scraping keeps CPU above the idle-reclamation
floor (Oracle reclaims instances under ~20% CPU p95 over 7 days), which mitigates the main risk.

**Paid fallback: Contabo Cloud VPS 10 (Singapore), ~$5/mo, 8 GB.** If Oracle's ARM-capacity
provisioning or reclamation becomes annoying, this is the cheap, reliable backstop: 8 GB fits
the whole monitoring stack with headroom, Singapore keeps latency low, ~$5/mo. Budget-tier I/O
and support are the accepted trade-off for a single-user app.

**Rock-bottom paid alt: RackNerd 4 GB annual (~$3.66/mo, prepaid ~$44/yr)** if every dollar
counts and prepaying is fine (4 GB means trimming Prometheus retention / skipping on-box Grafana).

Arch note: ARM64 (Oracle) is fine — the images we use (pgvector, redis, prometheus, grafana,
python, node) are all multi-arch.

## Consequences

- **Good:** $0 baseline honors the cost priority and AGENTS.md's "keep cost minimal"; a clear
  paid fallback de-risks the free-tier caveats. SEA latency addressed by region choice.
- **Recurring cost:** $0 (Oracle) or ~$5/mo (Contabo) — within the AGENTS.md "one small VPS"
  budget. This is the only recurring infra bill; flagged per the cost rule and accepted.
- **Constraint:** Oracle ARM capacity can require retries to provision; if it can't be secured,
  fall straight to Contabo. ARM means arm64 images (already satisfied).
- **Deferred:** the live deploy itself is a runbook (`docs/runbooks/deploy-checklist.md`),
  executed when the box is provisioned — not in this phase.

## Alternatives considered

- **Hetzner CX22 (~$4.85/mo, 4 GB).** Best-engineered box and the original plan default, but
  **EU/US-only** — ~150–180 ms from Vietnam for a daily-use UI, and at 4 GB no cheaper than
  Contabo's 8 GB. The right pick only if the owner relocates to EU/US.
- **DigitalOcean / Vultr / Linode (~$20–24/mo, 4 GB).** Best docs/DX and Asia regions, but
  4–5× the cost — fails the low-cost priority.
- **Netcup (EU, ~€3–4 entry).** Good value but EU-only latency and recently price-raised; no
  Asia edge over Contabo.
