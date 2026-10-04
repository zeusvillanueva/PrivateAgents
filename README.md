# PrivateAgents

A minimal Python agent hosted by **Azure AI Foundry**, designed for Microsoft
Teams and **Microsoft 365 Copilot**. It uses the Foundry Responses protocol and
Entra authentication, not API keys. No organizational tools or data sources are
connected by default.

## Security and privacy boundary

```text
Teams / Microsoft 365 Copilot
  -> Foundry's authenticated, source-IP-filtered public Activity Protocol route
  -> Foundry hosted agent in a delegated VNet subnet
  -> private Foundry project and model endpoint
```

`infra/main.bicep` provisions a new network-injected Foundry account, project,
model, capability host, Premium container registry, private endpoints, and
private DNS. Public access is disabled on Foundry and the registry; local-key
authentication and registry admin credentials are disabled. The project identity
gets `AcrPull` only on this registry. A NAT gateway supports outbound connections
(including Entra authentication); its public IP provides **no inbound listener**.
This is private ingress, **not an outbound allowlist**. For production, route
egress through an organization-managed firewall and permit only required
destinations. Choose nonoverlapping network ranges before connecting to an
existing network.

**Teams and Copilot cannot connect through Private Link.** Publishing requires
the Foundry-managed `enable_m365_public_endpoint` exception for Activity Protocol
only. Source-IP filtering does not replace authentication: this guide retains
Entra authorization and uses `BotServiceRbac`, with `Shared` publishing scope.
Other protocols and management APIs remain private. If policy forbids *any*
publicly routable agent endpoint, do not publish to these channels.

The agent disables additional model-side response storage (`store=False`) and
OpenTelemetry SDK export by default. This does **not** promise zero retention:
the hosting adapter maintains session/response state, Foundry manages hosted
sessions, and Teams/Microsoft 365 process and store channel data under their own
terms and residency commitments. Review retention, tenant policies, access, and
data residency before publishing. Do not put credentials or sensitive data in
instructions, environment configuration, app metadata, or logs.

## Prerequisites

- Azure CLI 2.80+, Bicep, Docker, and `jq`.
- A subscription/region supporting hosted agents and the selected model with
  sufficient quota. The template defaults to a regional `Standard` model SKU;
  verify availability rather than silently switching to global processing.
- Permission to deploy resources and assign roles. Register
  `Microsoft.CognitiveServices`, `Microsoft.Network`,
  `Microsoft.ContainerRegistry`, and `Microsoft.BotService`.
- A **new** Foundry account: hosted-agent network injection cannot be retrofitted.
  Private registry support requires a project created after June 25, 2026.
- For data-plane deployment and publishing, run from a workstation or runner
  connected to the VNet through VPN, ExpressRoute, or peering, with private DNS
  resolution. This template does not provision that connectivity or a runner.
- Grant the deployment identity **Foundry Project Manager** on the project and
  `AcrPush` on the registry. Grant intended users the project permissions required
  to invoke agents. Bot creation also requires Bot Service resource permissions.
  Foundry creates the runtime agent identity with default model access; grant
  additional resource roles only if you add tools.

## 1. Provision private infrastructure

Commands use this checkout's absolute path; adjust `REPO` for another checkout.
Choose a supported region and a lowercase alphanumeric prefix.

```bash
export REPO=/home/runner/work/PrivateAgents/PrivateAgents
export RG=private-agents
export LOCATION=eastus
az login
az group create --name "$RG" --location "$LOCATION"
az deployment group create --name privateagents --resource-group "$RG" \
  --template-file "$REPO/infra/main.bicep" \
  --parameters namePrefix=privateagents location="$LOCATION"

export PROJECT_ENDPOINT=$(az deployment group show -g "$RG" -n privateagents \
  --query properties.outputs.projectEndpoint.value -o tsv)
export ACR=$(az deployment group show -g "$RG" -n privateagents \
  --query properties.outputs.registryName.value -o tsv)
export REGISTRY=$(az deployment group show -g "$RG" -n privateagents \
  --query properties.outputs.registryLoginServer.value -o tsv)
export MODEL=$(az deployment group show -g "$RG" -n privateagents \
  --query properties.outputs.modelDeploymentName.value -o tsv)
export AGENT=private-agent
```

Before continuing, resolve both `$REGISTRY` and the project endpoint hostname
from your connected runner and confirm they resolve to private IP addresses.
Allow time for identity role assignments to propagate.

## 2. Build and deploy the hosted agent

Build and push **from the private-network-connected runner**. Use a unique image
tag for each release; never rebuild a tag used by an active version.

```bash
export IMAGE="$REGISTRY/private-agent:0.1.0"
az acr login --name "$ACR"
docker build --platform linux/amd64 --tag "$IMAGE" "$REPO/src/private_agent"
docker push "$IMAGE"

az rest --method post --resource https://ai.azure.com \
  --url "$PROJECT_ENDPOINT/agents?api-version=v1" \
  --body "$(jq -n --arg name "$AGENT" --arg image "$IMAGE" --arg model "$MODEL" '{
    name: $name,
    definition: {
      kind: "hosted",
      container_configuration: {image: $image},
      cpu: "1", memory: "2Gi",
      protocol_versions: [{protocol: "responses", version: "2.0.0"}],
      environment_variables: {
        MODEL_DEPLOYMENT_NAME: $model,
        OTEL_SDK_DISABLED: "true"
      }
    }
  }')"
```

Foundry supplies `FOUNDRY_PROJECT_ENDPOINT` and the runtime identity; do not
override platform-injected variables or add API keys. Creating the agent creates
version `1`. Check its status until `active`; stop on `failed` and inspect `error`.
Do not route traffic or publish an untested version.

```bash
az rest --resource https://ai.azure.com \
  --url "$PROJECT_ENDPOINT/agents/$AGENT/versions/1?api-version=v1" \
  --query '{status:status,error:error}'

# Run only after the version becomes active.
az rest --method patch --resource https://ai.azure.com \
  --url "$PROJECT_ENDPOINT/agents/$AGENT?api-version=v1" \
  --headers Content-Type=application/merge-patch+json \
  --body '{
    "agent_endpoint": {
      "version_selector": {"version_selection_rules": [
        {"type":"FixedRatio","agent_version":"1","traffic_percentage":100}
      ]},
      "protocol_configuration": {"responses":{}},
      "authorization_schemes": [{"type":"Entra"}]
    }
  }'

az rest --method post --resource https://ai.azure.com \
  --url "$PROJECT_ENDPOINT/agents/$AGENT/endpoint/protocols/openai/responses?api-version=v1" \
  --body '{"input":"What can you help me with?","stream":false,"store":false}'
```

These configuration examples target a **new agent**. Endpoint PATCH replaces
protocol and authorization collections: for an existing agent, GET its
configuration first and retain every required protocol and authorization scheme.
For upgrades, POST the new definition to `/agents/$AGENT/versions?api-version=v1`,
test the returned version, then explicitly update the pinned version selector.

## 3. Connect Teams and Microsoft 365 Copilot

After testing the active version, obtain the agent's **client ID**, then create
the channel registration. The Bot Service is channel plumbing; the agent still
runs on Foundry hosted compute.

```bash
export AGENT_CLIENT_ID=$(az rest --resource https://ai.azure.com \
  --url "$PROJECT_ENDPOINT/agents/$AGENT?api-version=v1" \
  --query instance_identity.client_id -o tsv)
export BOT_NAME="private-agent-$(az account show --query id -o tsv | cut -c1-8)"

az deployment group create --name privateagents-bot --resource-group "$RG" \
  --template-file "$REPO/infra/bot.bicep" \
  --parameters botName="$BOT_NAME" agentClientId="$AGENT_CLIENT_ID" \
    activityEndpoint="$PROJECT_ENDPOINT/agents/$AGENT/endpoint/protocols/activityProtocol?api-version=2025-05-15-preview"

export BOT_ID=$(az deployment group show -g "$RG" -n privateagents-bot \
  --query properties.outputs.botServiceArmId.value -o tsv)

# Explicitly opt into the channel-only public route.
az rest --method patch --resource https://ai.azure.com \
  --url "$PROJECT_ENDPOINT/agents/$AGENT?api-version=v1" \
  --headers Content-Type=application/merge-patch+json \
  --body '{
    "agent_endpoint": {
      "protocol_configuration": {
        "responses":{},
        "activity":{"enable_m365_public_endpoint":true}
      },
      "authorization_schemes":[{"type":"Entra"},{"type":"BotServiceRbac"}]
    }
  }'
```

Set these to your organization's **actual approved public metadata and policies**,
not Foundry credentials or Microsoft policies presented as your own:
`DEVELOPER_NAME`, `DEVELOPER_URL`, `PRIVACY_URL`, and `TERMS_URL`.

```bash
az rest --method post --resource https://ai.azure.com \
  --url "$PROJECT_ENDPOINT/agents/$AGENT/microsoft365/publish?api-version=v1" \
  --body "$(jq -n --arg bot "$BOT_ID" \
    --arg developer "${DEVELOPER_NAME:?Set your developer name}" \
    --arg website "${DEVELOPER_URL:?Set your developer URL}" \
    --arg privacy "${PRIVACY_URL:?Set your privacy policy URL}" \
    --arg terms "${TERMS_URL:?Set your terms URL}" '{
      agentDisplayName: "Private Agent", botServiceArmId: $bot,
      publishScope: "Shared", publishAsAutopilot: false, appVersion: "1.0.0",
      shortDescription: "Organizational assistant hosted in Foundry.",
      fullDescription: "An identity-authenticated organizational assistant.",
      developerName: $developer, developerWebsiteUrl: $website,
      privacyUrl: $privacy, termsOfUseUrl: $terms
    }')"
```

The API returns a `titleId`; verify the agent appears under **Your agents** and
test it in both Teams and Copilot. `Shared` is intentionally limited; do not
switch to `Tenant` without approval—it changes authorization to
`BotServiceTenant`, allowing everyone in your tenant. Increment `appVersion`
when republishing metadata. To inspect or manually upload a generated app
package, use the documented `/microsoft365/zip` endpoint with the same body.

## Validation

There was no existing test/lint infrastructure. Compile the templates and smoke
test the real hosting adapter locally:

```bash
bicep build "$REPO/infra/main.bicep" --outfile /tmp/privateagents-main.json
bicep build "$REPO/infra/bot.bicep" --outfile /tmp/privateagents-bot.json

docker run --rm -p 127.0.0.1:8088:8088 \
  -e FOUNDRY_PROJECT_ENDPOINT="$PROJECT_ENDPOINT" \
  -e MODEL_DEPLOYMENT_NAME="$MODEL" \
  "$IMAGE"
# In another terminal:
curl --fail http://127.0.0.1:8088/readiness
```

Local readiness does not exercise model authentication. For local authenticated
inference, install the Python project in a virtual environment, `az login` from
a connected workstation, and run `src/private_agent/main.py` by its absolute
path with `FOUNDRY_PROJECT_ENDPOINT`, `MODEL_DEPLOYMENT_NAME`, and
`OTEL_SDK_DISABLED=true` set. Do not expose the local adapter directly to the
internet; production authentication is enforced by the Foundry gateway.

Before production, verify:

- Authenticated private-endpoint inference succeeds; unauthenticated requests
  fail. Management and Responses requests from outside the VNet are blocked.
- Teams/Copilot work for authorized users; another tenant and users lacking
  invocation roles cannot invoke the agent.
- The registry's public endpoint is blocked and Foundry can pull privately.
- No prompts/responses appear in telemetry exports; review all platform and
  Microsoft 365 retention separately. The SDK writes session state under its
  state directory (default `~/.agentserver`); never bake it into an image.

Azure provisioning, quota, private image pulls, and channel integration need
live subscription/tenant validation; compilation and local readiness alone do
not establish these guarantees. Remove the published app through Microsoft 365
administration before deleting the resource group with `az group delete`.

## References

- [Hosted-agent deployment and runtime contract](https://learn.microsoft.com/azure/foundry/agents/how-to/deploy-hosted-agent)
- [Private-network Teams/Copilot publishing and its security boundary](https://learn.microsoft.com/azure/foundry/agents/how-to/publish-copilot-virtual-network)
- [Foundry networking options](https://learn.microsoft.com/azure/foundry/agents/concepts/networking-options)
