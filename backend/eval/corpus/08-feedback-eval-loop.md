# Feedback eval loop

Negative answer feedback is treated as review input, not an automatic training signal. The
feedback review page shows the original question, answer, retrieval context, and cited document
titles. A reviewer can promote a candidate only after confirming expected documents, expected
keywords, and refusal behavior. Promotion requires both the normal API bearer token and the
`X-Second-Brain-Admin-Token` admin header. Reviewed cases are stored in the durable `eval_cases`
Postgres table and audited. The running API never mutates `backend/eval/dataset.yaml`; operators
export staged cases with `python -m app.eval.export_cases` and commit dataset changes deliberately.
