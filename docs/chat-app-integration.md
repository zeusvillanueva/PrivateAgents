# Chat app integration

How `../PIAIAgentsChatApp` finds and calls these agents. Follow this whenever an agent is added or changed.

## How the chat app works
- The agent list comes from the chat app's Cosmos DB `agents` container, **not** from Foundry. Registering an agent in Foundry does not make it appear in the app.
- It calls `AZURE_FOUNDRY_PROJ_ENDPOINT` (the platform Foundry project, `.../api/projects/agents`) using the Responses API with `agent: {name, type: 'agent_reference'}`. Hosted agents are detected and called through their agent endpoint, streaming or not.
- It authenticates with its web app managed identity (`USE_MANAGED_IDENTITIES=true`).

## Checklist for every agent
1. **Name:** Foundry agent name is `<folder>-agent` (e.g. `analyst-agent`). Add the agent on the chat app's Agents page (or the Cosmos `agents` container) with `name` set to exactly that. A mismatch gives "agent not found".
2. **Same project:** the chat app's `AZURE_FOUNDRY_PROJ_ENDPOINT` and this repo's `AZURE_AI_PROJECT_ENDPOINT` must be the same project.
3. **Registered and active:** `python scripts/register_agents.py` (or the CI `register` job) created a version with status `active`. Check the Foundry portal or `GET .../agents?api-version=v1`.
4. **Access:** the chat app's managed identity has `Foundry User` on the Foundry account/project (platform `appIdentities` role `foundry`).
5. **Protocol:** hosted `responses` protocol, served on port 8088 by `from_agent_framework(agent).run()`.
6. **No prompt-agent clash:** build the model client with `shared/config.py` (`AzureOpenAIResponsesClient`). Do not use `AzureAIClient(agent_name=...)`: it creates a prompt agent version of the same name and fails with "Agent kind mismatch ... Existing: hosted, New: prompt".
7. **Attachments:** keep the `<attachments>{...}</attachments>` contract in [README](README.md) in sync with the chat app.
8. **Files:** never return `sandbox:/mnt/data/...` links. Use `GeneratedFilesMiddleware` (https SAS links via `STORAGE_ACCOUNT_URL`). The agent's instance identity needs Storage Blob Data Contributor on the `agent-files` container and Storage Blob Delegator on the storage account (platform-owned). The chat app renders markdown images and allows links.
9. **Description:** add a `DESCRIPTIONS` entry in `scripts/register_agents.py`; use the same text as the chat app agent description.

10. **Orchestrator:** `orchestrator-agent` is planner-only; the chat app must run its plans and may select only one active orchestrator. See [orchestrator](orchestrator.md).

## Smoke test
    python - <<'PY'
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential
    c = AIProjectClient(endpoint="<AZURE_AI_PROJECT_ENDPOINT>", credential=DefaultAzureCredential())
    print(c.get_openai_client(agent_name="assistant-agent").responses.create(input="Say hello").output_text)
    PY
Then send a message to the agent from the chat app.
