# Hosted agents

Python hosted agents for Azure AI Foundry, built with Microsoft Agent Framework + `azure-ai-agentserver`.

| Agent | Tooling | Purpose |
|---|---|---|
| `agents/assistant` | File search (vector store) | Grounded Q&A over uploaded docs; falls back to LLM knowledge |
| `agents/analyst` | Code interpreter | Dataset analysis; charts via code interpreter; Word/PowerPoint/PDF/Excel via container-side tools (`shared/documents.py`) |
| `agents/orchestrator` | None (planner only) | Plans tasks over eligible published agents, evaluates results, synthesises the final answer |

The orchestrator never invokes other agents itself: hosted agents cannot call each other. It replies with JSON plans
(`{"tasks": [{"id","agent","prompt","depends_on","expected_output"}]}`), and the chat app backend validates them against
the published-agent registry and user permissions, runs tasks (parallel/sequential, bounded), and sends results back for
evaluation and synthesis. The chat app passes eligible agents as `<agents>[{"name","description"}]</agents>`.

## Attachment contract (chat app -> agent)
The chat app uploads files to Foundry (Files API / vector store) and prepends to the user message:

    <attachments>{"vector_store_ids": ["vs_123"], "file_ids": ["file-abc"]}</attachments>

Assistant uses `vector_store_ids`; Analyst uses `file_ids`. IDs are validated and the block is stripped before the model sees it.
Documents: `create_word`/`create_powerpoint`/`create_pdf`/`create_excel` build files from structured input (python-docx, python-pptx, reportlab, openpyxl), upload them to blob storage and return a markdown link (25 MB cap, correct MIME and Content-Disposition).
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
Pushes to `main` deploy all agents; manual runs (workflow_dispatch) offer an `all` checkbox plus one per agent. They run `.github/workflows/build-agents.yml`: test, build/push images to ACR, then register a hosted agent
version per image with `python scripts/register_agents.py` (also runnable locally after `az login`, with the `.env.example`
vars plus `ACR_LOGIN_SERVER` and optional `IMAGE_TAG`). Hosted agents are in preview; the project identity needs AcrPull
(granted by the platform) and the runtime identity "Azure AI User" on the project. The script's protocol version
(`responses` / `1.0.0`) and cpu/memory are defaults; confirm against current Foundry docs on first deploy.
See [infrastructure](infrastructure.md) for the shared platform resources this depends on.
