# Hosted agents

Two Python hosted agents for Azure AI Foundry, built with Microsoft Agent Framework + `azure-ai-agentserver`.

| Agent | Tooling | Purpose |
|---|---|---|
| `agents/assistant` | File search (vector store) | Grounded Q&A over uploaded docs; falls back to LLM knowledge |
| `agents/analyst` | Code interpreter | Dataset analysis; generates charts, PDF, Office files |

## Attachment contract (chat app -> agent)
The chat app uploads files to Foundry (Files API / vector store) and prepends to the user message:

    <attachments>{"vector_store_ids": ["vs_123"], "file_ids": ["file-abc"]}</attachments>

Assistant uses `vector_store_ids`; Analyst uses `file_ids`. IDs are validated and the block is stripped before the model sees it.
Generated files: the hosted agent server drops file annotations, so the analyst's `GeneratedFilesMiddleware`
(`shared/generated_files.py`) downloads each file from the code interpreter container and appends it to the reply as
markdown (`![name](url)` for images, `[Download name](url)` otherwise; 5 MB cap). With `STORAGE_ACCOUNT_URL` set the file is
uploaded to the `agent-files` container and linked with a 7-day user-delegation SAS URL (works in the Foundry playground
and the chat app). Without it, files are embedded as base64 `data:` URIs, which the playground will not render.
Requirements: the agent's instance identity needs Storage Blob Data Contributor on the container and Storage Blob Delegator
on the storage account (platform resources; see [infrastructure](infrastructure.md)).

See [chat-app-integration](chat-app-integration.md) for what the chat app needs to load and use these agents.

## Run locally
    python -m venv .venv && . .venv/bin/activate
    pip install --pre -r requirements.txt pytest
    cp .env.example .env   # then export values; az login
    PYTHONPATH=. python agents/assistant/main.py   # serves on :8088
    PYTHONPATH=. pytest tests

## Deploy
Pushes to `main` run `.github/workflows/build-agents.yml`: test, build/push images to ACR, then register a hosted agent
version per image with `python scripts/register_agents.py` (also runnable locally after `az login`, with the `.env.example`
vars plus `ACR_LOGIN_SERVER` and optional `IMAGE_TAG`). Hosted agents are in preview; the project identity needs AcrPull
(granted by the platform) and the runtime identity "Azure AI User" on the project. The script's protocol version
(`responses` / `1.0.0`) and cpu/memory are defaults; confirm against current Foundry docs on first deploy.
See [infrastructure](infrastructure.md) for the shared platform resources this depends on.
