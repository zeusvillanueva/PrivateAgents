# Agent builder

`agents/agent-builder` (Foundry name `agent-builder-agent`) interviews a user and produces a JSON definition for a new
**prompt agent**. It has no tools and creates nothing; the chat app (`../PIAIAgentsChatApp`) validates the JSON and
creates the agent after the user confirms.

## Message contract
Every call carries `<phase>build</phase>`, the conversation so far, and server-supplied context:
- `<deployments>["gpt-4o", ...]</deployments>` model deployments the agent may use.
- `<tools>["file_search","code_interpreter","web_search","mcp"]</tools>` tool types allowed.
- `<agents>["existing-agent-name", ...]</agents>` names already taken.

Reply is ONLY one JSON object (no prose, no code fences):

    {"status": "ask", "message": "<one or two short questions or a clarification>"}

    {"status": "ready", "message": "<one-line summary for the user to confirm>",
     "agent": {"name": "<display name>", "description": "<one sentence>", "instructions": "<system prompt>",
               "deployment": "<exact value from deployments>",
               "tools": [{"type": "web_search"}, {"type": "code_interpreter"}, {"type": "file_search"},
                         {"type": "mcp", "server_label": "<letters/numbers/_/->", "server_url": "https://...",
                          "require_approval": "always"}],
               "needsKnowledgeFiles": false}}

Without a `<phase>build</phase>` tag the agent answers as a normal chat agent (never JSON).

## Rules the app enforces (the builder respects them; the app never relies on it)
- `name` becomes the Foundry name (lowercase, hyphens) and must not be in `<agents>`. `description` and `instructions` required.
- `deployment` must be exactly one of `<deployments>`. Max 8 tools, no duplicates, only types in `<tools>`.
- `file_search` needs knowledge files: `needsKnowledgeFiles: true`; the app asks for uploads and supplies the vector
  store. The builder never invents vector store ids.
- `mcp` URLs must be https without credentials; `require_approval` defaults to `always`, never `never` unless the user explicitly asks.
- Prompt agents only; never `kind`, images, CPU, memory or env vars.

## Rollout
1. Run `build-agents` (select `agent-builder`) to build and register the image.
2. Add `agent-builder-agent` on the chat app's Agents page (exact name).
3. Smoke test per [chat-app-integration](chat-app-integration.md), sending `<phase>build</phase>` plus sample context.
