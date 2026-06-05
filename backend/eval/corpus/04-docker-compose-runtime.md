# Docker Compose runtime

The production runtime is a single Docker Compose stack on one small VPS (~$4–6/month), not
Kubernetes — a single-user app does not need multi-node scheduling or autoscaling. Every
service runs as a container: the FastAPI backend, the Next.js frontend, Postgres with the
pgvector extension, and Redis for caching. Locally the database builds the repo's pgvector image
and publishes on host port 5433, because a native PostgreSQL already occupies the default 5432.
Keeping the whole stack in Compose makes the deployment cheap, reproducible, and easy to
bring up with a single `docker compose up -d`.
