# Briefing worker queue

Background work uses the durable Postgres `jobs` table. OS cron or a local scheduler enqueues a
briefing job, and the worker process drains queued jobs with `python -m app.jobs.worker --loop`.
Briefings summarize documents ingested since the previous briefing period, then store markdown for
display in the web app. Empty windows produce a "nothing new" briefing without calling the LLM.
The same worker path also handles async research jobs, so research can be queued and retried
without blocking the API request.
