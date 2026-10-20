# AGENTS.md

Guidance for AI coding agents working in this repo.

## Purpose
Hosted Foundry agents (Microsoft Agent Framework, Python) for Teams/Copilot, loaded by `../PIAIAgentsChatApp`. See [README.md](README.md) and [docs/](docs/README.md).

## Principles
- **No infra here.** Shared Azure resources (Foundry project, model, ACR, RBAC) are owned by `../AIAgentsPlatformInfra`. Only app-specific pieces live here: agent code, Dockerfiles, `.github/workflows/build-agents.yml`. See [docs/infrastructure.md](docs/infrastructure.md).
- **Identity over keys.** Use `DefaultAzureCredential`; never commit secrets. CI uses GitHub OIDC.
- **Config via env** (`.env.example`); values come from platform outputs (`foundryProjectEndpoint`, `acrName`). Don't hard-code endpoints or deployment names.
- Keep the attachment contract (`docs/README.md`) in sync with the chat app.
- **The chat app must be able to load every agent.** See the checklist in [docs/chat-app-integration.md](docs/chat-app-integration.md). Key rules: Foundry agent name == `<name>-agent` == the chat app's Cosmos agent `name`; hosted `responses` protocol only; never use `AzureAIClient(agent_name=...)` (it creates a conflicting prompt agent); return files as https links, not `sandbox:` paths.

## Conventions
- New agent: `agents/<name>/{main.py,Dockerfile,requirements.txt}`, add to the workflow matrix, `AGENTS` in `scripts/register_agents.py` (with a description) and docs, then follow the chat app checklist.
- Run `PYTHONPATH=. pytest tests` before committing.
- Update docs when agents, env vars or platform dependencies change.

## Related repos
- `../AIAgentsPlatformInfra` – shared infra (change roles/resources there).
- `../PIAIAgentsChatApp` – consumer chat app.
