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
Generated files come back as file annotations in the response; the chat app should proxy-download them.

## Run locally
    python -m venv .venv && . .venv/bin/activate
    pip install --pre -r requirements.txt pytest
    cp .env.example .env   # then export values; az login
    PYTHONPATH=. python agents/assistant/main.py   # serves on :8088
    PYTHONPATH=. pytest tests

## Deploy
Build each Dockerfile from the repo root (`docker build -f agents/<name>/Dockerfile .`), push to ACR, and register as a
hosted agent in your Foundry project (e.g. `azd ai agent` / portal). Grant the agent identity "Azure AI User" on the
project and AcrPull on the registry. Hosted agents are in preview; confirm current deploy steps in the Foundry docs.
