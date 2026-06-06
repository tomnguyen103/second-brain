# MCP local tools

The MCP server runs over stdio for trusted local clients. It exposes read-oriented tools such as
`search_notes`, `list_tasks`, and `send_digest` by default. Durable mutations are guarded by
`SECOND_BRAIN_MCP_ENABLE_MUTATIONS`; when that flag is false, tools like `create_task` and
`research_topic` are refused. This keeps local automation useful while preventing an MCP client
from silently writing tasks or research notes unless the operator explicitly opts in.
