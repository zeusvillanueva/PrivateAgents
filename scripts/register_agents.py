"""Register ACR images as Foundry hosted agent versions.

Env: AZURE_AI_PROJECT_ENDPOINT, AZURE_AI_MODEL_DEPLOYMENT_NAME, ACR_LOGIN_SERVER, IMAGE_TAG (default latest),
STORAGE_ACCOUNT_URL (optional; generated files are uploaded there and linked with SAS URLs),
IMAGE_PROJECT_ENDPOINT + IMAGE_MODEL_DEPLOYMENT_NAME (optional; image-creator, from platform output `foundryImagesProjectEndpoint`).
Usage: python scripts/register_agents.py [assistant analyst orchestrator agent-builder markdown diagram-creator image-creator sharepoint]
"""
import os
import sys

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    ContainerConfiguration,
    HostedAgentDefinition,
    ProtocolVersionRecord,
)
from azure.identity import DefaultAzureCredential

DESCRIPTIONS = {
    "assistant": "Answers questions using uploaded documents (file search), or general knowledge when none are provided.",
    "analyst": "Analyses uploaded datasets with code interpreter and generates charts, PDFs and Office documents.",
    "orchestrator": "Plans which published agents to use, evaluates their results and synthesises the final answer.",
    "agent-builder": "Interviews you about the agent you want and prepares its definition for creation in the chat app.",
    "markdown": "Writes Markdown documents (READMEs, specs, runbooks, ADRs, notes).",
    "diagram-creator": "Creates and fixes Mermaid diagrams (flowchart, sequence, class, ER, state, Gantt, mindmap).",
    "image-creator": "Creates images from text descriptions using the platform's gpt-image-2 deployment.",
    "sharepoint": "Searches a SharePoint site as the signed-in user (checks access and permission level) and answers from the top 10 results.",
}
AGENTS = list(DESCRIPTIONS)


def main(names: list[str]) -> None:
    endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
    model = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
    registry = os.environ["ACR_LOGIN_SERVER"]
    tag = os.environ.get("IMAGE_TAG", "latest")

    env_vars = {"AZURE_AI_PROJECT_ENDPOINT": endpoint, "AZURE_AI_MODEL_DEPLOYMENT_NAME": model}
    if os.environ.get("STORAGE_ACCOUNT_URL"):
        env_vars["STORAGE_ACCOUNT_URL"] = os.environ["STORAGE_ACCOUNT_URL"]
    for key in ("IMAGE_PROJECT_ENDPOINT", "IMAGE_MODEL_DEPLOYMENT_NAME"):
        if os.environ.get(key):
            env_vars[key] = os.environ[key]

    client = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())
    for name in names:
        agent_name = f"{name}-agent"
        version = client.agents.create_version(
            agent_name,
            description=DESCRIPTIONS[name],
            definition=HostedAgentDefinition(
                cpu="1",
                memory="2Gi",
                container_configuration=ContainerConfiguration(image=f"{registry}/{agent_name}:{tag}"),
                protocol_versions=[ProtocolVersionRecord(protocol="responses", version="1.0.0")],
                environment_variables=env_vars,
            ),
        )
        print(f"Registered {agent_name} version {version.version}")


if __name__ == "__main__":
    main(sys.argv[1:] or AGENTS)
