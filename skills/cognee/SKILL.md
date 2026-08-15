# Cognee Cloud Memory Skill

This skill connects your AI agent to Cognee Cloud for persistent knowledge graph memory.

## First — is memory already automatic here?

If the Cognee Claude Code plugin or an MCP server is installed, memory works on its own: relevant context is recalled into your prompt each turn, and your turns are captured and converted to long-term memory for you. When that is the case:
- Do NOT call the HTTP API manually (no curl), and do NOT narrate routine recalls/saves.
- Use the provided memory skills/tools (e.g. cognee-search / cognee-remember) only for an explicit deep search or a "remember this permanently" request.

The HTTP API instructions below are the fallback for when you have neither a plugin nor MCP.

## Prerequisites
- Cognee Cloud account with API key
- Environment variables set:
  - `COGNEE_BASE_URL` — your tenant API endpoint
  - `COGNEE_API_KEY` — your API key

**If these variables are not set**, ask the user to run the export commands from the Cognee Cloud console (Integrations → API / MCP → Step 1).

## ALWAYS ping Cognee Cloud first

Before any other operation in the conversation, ping Cognee Cloud to confirm the env vars are valid and the tenant is reachable. If the ping fails (non-200, network error, or auth error), tell the user immediately and ask them to re-export the credentials from the Cognee Cloud console — do NOT proceed with remember/recall calls against a broken connection.

```bash
curl -fsS -o /dev/null -w "%{http_code}" \
  "$COGNEE_BASE_URL/api/v1/datasets/" \
  -H "X-Api-Key: $COGNEE_API_KEY"
```
A `200` means the connection works. A `401` means the API key is wrong; `404`/`5xx` means the tenant URL is wrong or the service is down.

## Session ID — ALWAYS use one

At the start of the conversation, generate ONE id (a unix-timestamp-based id unique to this conversation, e.g. "1719320000") and reuse it as `session_id` in every call. Sessions group your activity in the Cognee Cloud dashboard and are converted into long-term memory. The ONLY exception: when the user explicitly asks you to store something directly in the knowledge graph, call /remember without a session_id.

## Operations

### Remember — Store knowledge
When the user shares important information worth preserving:
```bash
# Default: store as a session entry — always include your session_id
curl -X POST $COGNEE_BASE_URL/api/v1/remember/entry \
  -H "X-Api-Key: $COGNEE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"entry": {"type": "qa", "question": "<topic or user question>", "answer": "<the knowledge to store>"}, "dataset_name": "default_dataset", "session_id": "<session-id>"}'
```

### Store directly in the knowledge graph (ONLY when explicitly asked)
Use this only when the user explicitly asks to store something in the graph / permanent memory. The data must be a FILE upload (inline text is rejected with 422) and must NOT include a session_id:
```bash
TMP=$(mktemp) && printf '%s' "<text to store>" > "$TMP"
curl -X POST $COGNEE_BASE_URL/api/v1/remember \
  -H "X-Api-Key: $COGNEE_API_KEY" \
  -F "data=@$TMP;type=text/plain" \
  -F "datasetName=default_dataset"
rm -f "$TMP"
```

### Recall — Retrieve knowledge
Before answering questions, check if relevant knowledge exists:
```bash
curl -X POST $COGNEE_BASE_URL/api/v1/recall \
  -H "X-Api-Key: $COGNEE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "<user question>", "session_id": "<session-id>"}'
```

For targeted retrieval, add "search_type" to the recall body — one of: HYBRID_COMPLETION (default), GRAPH_COMPLETION, CHUNKS, GRAPH_SUMMARY_COMPLETION.

### List datasets
```bash
curl -s "$COGNEE_BASE_URL/api/v1/datasets/?session_id=<session-id>" -H "X-Api-Key: $COGNEE_API_KEY"
```

## Behavior
1. If a Cognee plugin or MCP server is active, memory is automatic — do NOT call the API manually, and do NOT narrate routine recalls/saves. The remaining guidelines apply only to the HTTP-API fallback.
2. At session start, verify COGNEE_BASE_URL and COGNEE_API_KEY are set; if not, ask the user to export them
3. **Ping Cognee Cloud** with the curl above before any other operation. If it doesn't return 200, surface the failure to the user and stop — do not proceed with broken credentials
4. Use one session id for the conversation (your agent name + a unix timestamp) as the `session_id` in every call — the session appears automatically in the Cognee Cloud dashboard under Sessions and is converted into long-term memory
5. Recall-first: when an answer may depend on earlier context, recall before answering
6. You do NOT need to store after every turn — the session is captured and converted to long-term memory automatically. Store explicitly only for durable facts worth keeping (via /remember/entry with your session_id); use /remember (file upload, no session_id) only when the user explicitly asks to write to the graph
7. Keep memory operations quiet — don't narrate routine recalls or saves
8. Use default_dataset unless specified otherwise
