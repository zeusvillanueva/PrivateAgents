# AGENTS.md

Guidance for AI coding agents working in this repo.

## Purpose
Hosted Foundry agents (Microsoft Agent Framework, Python) for Teams/Copilot, loaded by `../PIAIAgentsChatApp`. See [README.md](README.md) and [docs/](docs/README.md).

## Principles
- **No infra here.** Shared Azure resources (Foundry project, model, ACR, RBAC) are owned by `../AIAgentsPlatformInfra`. Only app-specific pieces live here: agent code, Dockerfiles, `.github/workflows/build-agents.yml`. See [docs/infrastructure.md](docs/infrastructure.md).
- **Identity over keys.** Use `DefaultAzureCredential`; never commit secrets. CI uses GitHub OIDC.
- **Config via env** (`.env.example`); values come from platform outputs (`foundryProjectEndpoint`, `acrName`). Don't hard-code endpoints or deployment names.
- Keep the attachment contract (`docs/README.md`) in sync with the chat app.

## Conventions
- New agent: `agents/<name>/{main.py,Dockerfile,requirements.txt}`, add to the workflow matrix and docs.
- Run `PYTHONPATH=. pytest tests` before committing.
- Update docs when agents, env vars or platform dependencies change.

## Related repos
- `../AIAgentsPlatformInfra` – shared infra (change roles/resources there).
- `../PIAIAgentsChatApp` – consumer chat app.
