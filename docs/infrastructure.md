# Infrastructure

PrivateAgents has **no infra of its own**. Everything shared is deployed by
[AIAgentsPlatformInfra](https://github.com/zeusvillanueva/AIAgentsPlatformInfra) (also used by PIAIAgentsChatApp).

| Need | Provided by | Platform output / param |
|---|---|---|
| Foundry account + project + model (`gpt-4.1`) | Platform `modules/foundry.bicep` | `foundryProjectEndpoint`, `foundryDeployments` |
| Container registry for agent images | Platform `modules/acr.bicep` (`deployAcr = true` in development) | `acrName`, `acrLoginServer` |
| ACR pull for hosted agents | Platform (project identity gets AcrPull) | automatic |
| CI identity: build/push + register agents | App-specific (GitHub OIDC app registration) | grant via platform `appIdentities` with roles `['foundry', 'acr']` |
| Chat app calling the agents | Platform `appIdentities` entry for PIAIAgentsChatApp with role `foundry` | — |

App-specific, not in the platform: agent code, Dockerfiles, `build-agents.yml` workflow, hosted-agent registration.

## Setup
1. Deploy the platform (`scripts/deploy.sh development <region>`); note `foundryProjectEndpoint` and `acrName`.
2. Create a dedicated Entra app registration (`privateagents-github-actions`, not the Foundry-managed `reg-aif-*` app) with
   federated credentials for the `development` environment. GitHub may send the immutable subject
   `repo:zeusvillanueva@<ownerId>/PrivateAgents@<repoId>:environment:development`, so add both it and
   `repo:zeusvillanueva/PrivateAgents:environment:development` (the failed login log shows the exact subject).
   Grant its service principal: `AcrPush` + `Reader` + `Contributor` on the registry (`az acr build` needs Contributor for
   `listBuildSourceUploadUrl`) and `Foundry User` on the `agents` project. Ideally via platform `appIdentities`.
3. In this repo create GitHub environment `development` with secrets `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`,
   `AZURE_SUBSCRIPTION_ID` and variables `ACR_NAME`, `ACR_LOGIN_SERVER`, `AZURE_AI_PROJECT_ENDPOINT`,
   `AZURE_AI_MODEL_DEPLOYMENT_NAME`, `STORAGE_ACCOUNT_URL` (platform outputs / `foundryDeployments`).
   (The workflow has an `environment` selector: `development` or `production`; a `production` environment needs its own federated credential and secrets/variables.)
4. Push to `main`: the workflow tests and builds `assistant-agent` / `analyst-agent` into the ACR.
5. The `register` job then creates a hosted agent version per image in the Foundry project
   (`scripts/register_agents.py`; the CI identity needs `Foundry User` on the project).
   Agent names (`assistant-agent`, `analyst-agent`) must match what the chat app calls.

## Generated files storage (analyst)
The analyst uploads generated files to the `agent-files` container of the platform storage account (lifecycle rule: delete
after 8 days). Each agent's instance identity needs `Storage Blob Data Contributor` on the container and
`Storage Blob Delegator` on the account. Instance identities are per agent and appear after the first registration
(`GET .../agents/<name>` -> `instance_identity.principal_id`); re-grant if an agent is deleted and recreated.
