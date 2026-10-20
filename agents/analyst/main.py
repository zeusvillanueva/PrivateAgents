from azure.ai.agentserver.agentframework import from_agent_framework

from agent_framework import Agent

from shared.attachments import Attachments, AttachmentToolsMiddleware
from shared.config import make_client
from shared.documents import DOCUMENT_TOOLS
from shared.generated_files import GeneratedFilesMiddleware

INSTRUCTIONS = """You are a data analyst. Use the code interpreter to analyse uploaded datasets.
- Inspect the data first (shape, columns, types, missing values) and state assumptions.
- Show key numbers in your reply and explain findings in plain language.
- Charts: save them as PNG files with the code interpreter; they are attached automatically.
- Documents: to deliver Word, PowerPoint, PDF or Excel files call create_word, create_powerpoint, create_pdf or
  create_excel with structured content (compute the numbers in the code interpreter first). Each returns a
  markdown download link: include it verbatim in your reply. Do not generate these files in the code interpreter.
- Never invent file links or paths (such as sandbox: links); only use links returned by tools.
- If no dataset is uploaded and one is needed, ask the user to upload it."""

client = make_client("analyst-agent")


def build_tools(attachments: Attachments) -> list:
    return [client.get_code_interpreter_tool(file_ids=attachments.file_ids or None)]


agent = Agent(
    client=client,
    name="analyst-agent",
    description="Analyses uploaded datasets with code interpreter and generates charts and documents.",
    instructions=INSTRUCTIONS,
    tools=DOCUMENT_TOOLS,
    middleware=[AttachmentToolsMiddleware(build_tools), GeneratedFilesMiddleware(client)],
)

if __name__ == "__main__":
    from_agent_framework(agent).run()
