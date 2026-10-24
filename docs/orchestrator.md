# Orchestrator agent

`agents/orchestrator` (Foundry name `orchestrator-agent`) decides which published agents should answer a request and
combines their results. It is a planner only: it has no tools and cannot call other agents, because hosted agents cannot
invoke each other. The chat app backend (`../PIAIAgentsChatApp`) is the orchestration runtime.

## Responsibilities
| Component | Responsibility |
|---|---|
| Orchestrator agent (this repo) | Understand the prompt, propose a task plan, evaluate results, synthesise the answer |
| Chat app backend | Validate plans, check publication/authorisation, run tasks (parallel/sequential), enforce limits, track execution |
| Cosmos DB agent registry (chat app) | Authoritative list of published agents and their metadata |
| Chat app configuration | Selects exactly one active orchestrator |

## Runtime sequence
1. Chat app authenticates the user and loads the active orchestrator plus the agents the user may use.
2. It calls `orchestrator-agent` with the prompt and `<agents>[{"name": "...", "description": "..."}]</agents>`.
3. The agent replies with a plan (below). The backend validates it: known and eligible agent names only, unique task ids,
   existing `depends_on` ids, no cycles, task/round limits.
4. Independent tasks run concurrently; dependent tasks run after their dependencies. Failed or unavailable tasks are
   reported, never replaced by invented calls.
5. Results go back to the orchestrator for evaluation; it may request a bounded number of follow-up tasks.
6. The backend asks for the final answer and returns it through the normal chat experience.

## Message contract
Planning reply (JSON only):

    {"tasks": [{"id": "t1", "agent": "assistant-agent", "prompt": "...", "depends_on": [], "expected_output": "..."}]}

`{"tasks": []}` means no agent is needed. Evaluation reply: `{"done": true}` or `{"done": false, "tasks": [...]}`.
Synthesis reply: prose that keeps citations and download links verbatim and states gaps, uncertainties and failed tasks.

The agent is told to use only names from the `<agents>` list, but the backend must not rely on that: always validate.

## Deploy and publish
- Built and registered like the other agents (`.github/workflows/build-agents.yml`, `scripts/register_agents.py`).
  Manual runs can pick `all` or individual agents.
- Add `orchestrator-agent` on the chat app's Agents page, then select it as the active orchestrator in the chat app
  configuration. Publishing and selecting the orchestrator are separate operations; neither deploys or deletes agents.
- Follow the [chat app checklist](chat-app-integration.md).

## Status
The agent is deployed. The runtime (plan validation, execution, limits, authorization, orchestrator selection) still has
to be implemented in the chat app.
