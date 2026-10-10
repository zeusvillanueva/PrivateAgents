from azure.ai.agentserver.agentframework import from_agent_framework

from agent_framework import Agent

from shared.attachments import Attachments, AttachmentToolsMiddleware
from shared.config import make_client

INSTRUCTIONS = """You are a data analyst. Use the code interpreter to analyse uploaded datasets.
- Inspect the data first (shape, columns, types, missing values) and state assumptions.
- Show key numbers in your reply and explain findings in plain language.
- When asked for charts, save them as PNG files. For reports, produce PDF (reportlab/matplotlib),
  Word (python-docx), Excel (openpyxl) or PowerPoint (python-pptx) files as requested, saved to disk
  so they are returned as downloadable files.
- If no dataset is uploaded and one is needed, ask the user to upload it."""

client = make_client("analyst-agent")


def build_tools(attachments: Attachments) -> list:
    return [client.get_code_interpreter_tool(file_ids=attachments.file_ids or None)]


agent = Agent(
    client=client,
    name="analyst-agent",
    description="Analyses uploaded datasets with code interpreter and generates charts and documents.",
    instructions=INSTRUCTIONS,
    middleware=[AttachmentToolsMiddleware(build_tools)],
)

if __name__ == "__main__":
    from_agent_framework(agent).run()
