# Local status panel

The local status panel separates reachability from authenticated operational details. `/health`
stays open and reports whether the API and database respond. The authenticated `/status` endpoint
reports the current Alembic migration version, the migration head, worker queue counts, indexed
source and document counts, chunk and embedding counts, and the configured LLM and embedding modes.
The worker status is derived from queued, running, done, and failed jobs; it is not a separate
worker heartbeat process. The frontend also shows whether an API bearer token is saved in the
browser.
