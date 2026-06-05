# Second Brain Case Study

This is the tight demo story for the project: a personal AI system that captures knowledge,
answers with citations, turns user feedback into reviewed eval cases, and blocks regressions with
an eval gate.

From `backend/`, seed the loop:

```bash
python -m app.demo.seed
```

## Flow 1: Capture to Searchable Knowledge

**User action:** save a web passage from `/capture` with a URL, title, selected text, notes, and
tags.

**System path:** `/capture` validates the URL without scraping it, creates a `bookmark` source,
stores the browser-provided text as a document, chunks it, embeds it, and invalidates hot search
cache entries.

**Proof to show:** the new source appears in `/sources`, the passage appears in `/search`, and a
chat question over that topic returns a cited answer with clickable source cards.

## Flow 2: Cited Chat to Quality Review

**User action:** ask a question in `/chat`, inspect the citations, then submit thumbs-down feedback
when an answer misses the mark.

**System path:** the backend retrieves hybrid Postgres results, buffers streaming LLM output until
citation/support validation passes, persists the assistant message and retrieval rows, and links the
feedback row to the answer and cited documents.

**Proof to show:** `/feedback` lists the negative example with the original question, answer,
retrieval context, and cited document titles. The review card pre-fills an eval candidate while
making the reviewer explicitly confirm expected sources, expected keywords, and refusal behavior.

## Flow 3: Feedback to Eval Gate

**User action:** promote one reviewed negative-feedback candidate from `/feedback` with the admin
token.

**System path:** the promotion endpoint validates the reviewed labels against the fixed eval corpus,
stores the case durably in the `eval_cases` Postgres table, and writes an audit row. The production
API does not mutate `backend/eval/dataset.yaml`; source-controlled eval changes remain deliberate
repo changes.

**Proof to show:** the promotion response reports `dataset_path: "postgres:eval_cases"`, the audit
log records `op: promote_eval_case`, and CI runs `python -m app.eval.gate` against the fixed YAML
dataset. When a staged case should become part of the release gate, export it:

```bash
python -m app.eval.export_cases --output eval/promoted-cases.yaml
```

Then copy the reviewed case into `backend/eval/dataset.yaml` as a normal repo change and let the
gate prove the retrieval and citation floor still holds.

## Why This Matters

The project is not just "RAG chat." It demonstrates a product loop:

1. Capture real knowledge.
2. Retrieve and answer with source-backed citations.
3. Collect quality feedback.
4. Convert feedback into reviewed eval data.
5. Use the eval gate to protect future changes.

That loop is the portfolio signal: user value, data modeling, retrieval quality, AI safety posture,
and release discipline in one small system.
