import os

from azure.identity import DefaultAzureCredential

from agent_framework.azure import AzureOpenAIResponsesClient


def make_client(agent_name: str) -> AzureOpenAIResponsesClient:
    """Responses client on the Foundry project; endpoint/model come from env.

    Deliberately not AzureAIClient: it creates a prompt agent version named `agent_name`, which
    conflicts with the hosted agent of the same name ("Agent kind mismatch").
    """
    return AzureOpenAIResponsesClient(
        project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
        deployment_name=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=DefaultAzureCredential(),
    )
