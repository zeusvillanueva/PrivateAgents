# Infrastructure

PrivateAgents has **no infra of its own**. Everything shared is deployed by
[AIAgentsPlatformInfra](https://github.com/zeusvillanueva/AIAgentsPlatformInfra) (also used by PIAIAgentsChatApp).

| Need | Provided by | Platform output / param |
|---|---|---|
| Foundry account + project + model (`gpt-4.1`) | Platform `modules/foundry.bicep` | `foundryProjectEndpoint`, `foundryDeployments` |
| Container registry for agent images | Platform `modules/acr.bicep` (`deployAcr = true` in poc) | `acrName`, `acrLoginServer` |
| ACR pull for hosted agents | Platform (project identity gets AcrPull) | automatic |
| CI identity: build/push + register agents | App-specific (GitHub OIDC app registration) | grant via platform `appIdentities` with roles `['foundry', 'acr']` |
| Chat app calling the agents | Platform `appIdentities` entry for PIAIAgentsChatApp with role `foundry` | — |

App-specific, not in the platform: agent code, Dockerfiles, `build-agents.yml` workflow, hosted-agent registration.

## Setup
1. Deploy the platform (`scripts/deploy.sh poc <region>`); note `foundryProjectEndpoint` and `acrName`.
2. Create an Entra app registration with federated credential `repo:zeusvillanueva/PrivateAgents:environment:poc`;
   add its object ID to the platform `appIdentities` with roles `['foundry', 'acr']` and redeploy.
3. In this repo create GitHub environment `poc` with secrets `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`,
   `AZURE_SUBSCRIPTION_ID` and variable `ACR_NAME`.
4. Push to `main`: the workflow tests and builds `assistant-agent` / `analyst-agent` into the ACR.
5. Register the images as hosted agents in the Foundry project (see [README](README.md#deploy)).
