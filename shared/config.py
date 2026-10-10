import os

from azure.identity import DefaultAzureCredential

from agent_framework_azure_ai import AzureAIClient


def make_client(agent_name: str) -> AzureAIClient:
    """Foundry client; endpoint/model come from env (injected by the hosting runtime)."""
    return AzureAIClient(
        project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
        model_deployment_name=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=DefaultAzureCredential(),
        agent_name=agent_name,
    )
