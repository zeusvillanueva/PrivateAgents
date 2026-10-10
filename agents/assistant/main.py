from azure.ai.agentserver.agentframework import from_agent_framework

from agent_framework import Agent

from shared.attachments import Attachments, AttachmentToolsMiddleware
from shared.config import make_client

INSTRUCTIONS = """You are a helpful assistant.
- If document search is available, search the uploaded documents first and ground your answer in them.
  Cite the source document names. If the documents do not contain the answer, say so clearly, then
  answer from general knowledge and label it as such.
- If no documents are available, answer from your general knowledge.
- Never invent citations."""

client = make_client("assistant-agent")


def build_tools(attachments: Attachments) -> list:
    if not attachments.vector_store_ids:
        return []
    return [client.get_file_search_tool(vector_store_ids=attachments.vector_store_ids)]


agent = Agent(
    client=client,
    name="assistant-agent",
    description="Answers questions using uploaded documents, or general knowledge when none are provided.",
    instructions=INSTRUCTIONS,
    middleware=[AttachmentToolsMiddleware(build_tools)],
)

if __name__ == "__main__":
    from_agent_framework(agent).run()
