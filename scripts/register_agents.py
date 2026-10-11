"""Register ACR images as Foundry hosted agent versions.

Env: AZURE_AI_PROJECT_ENDPOINT, AZURE_AI_MODEL_DEPLOYMENT_NAME, ACR_LOGIN_SERVER, IMAGE_TAG (default latest).
Usage: python scripts/register_agents.py [assistant analyst]
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

AGENTS = ["assistant", "analyst"]


def main(names: list[str]) -> None:
    endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
    model = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
    registry = os.environ["ACR_LOGIN_SERVER"]
    tag = os.environ.get("IMAGE_TAG", "latest")

    client = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())
    for name in names:
        agent_name = f"{name}-agent"
        version = client.agents.create_version(
            agent_name,
            definition=HostedAgentDefinition(
                cpu="1",
                memory="2Gi",
                container_configuration=ContainerConfiguration(image=f"{registry}/{agent_name}:{tag}"),
                protocol_versions=[ProtocolVersionRecord(protocol="responses", version="1.0.0")],
                environment_variables={
                    "AZURE_AI_PROJECT_ENDPOINT": endpoint,
                    "AZURE_AI_MODEL_DEPLOYMENT_NAME": model,
                },
            ),
        )
        print(f"Registered {agent_name} version {version.version}")


if __name__ == "__main__":
    main(sys.argv[1:] or AGENTS)
