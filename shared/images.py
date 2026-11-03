"""Image generation tool backed by the platform's gpt-image-2 deployment.

Env: IMAGE_PROJECT_ENDPOINT (platform output `foundryImagesProjectEndpoint`; only its host is used) and
IMAGE_MODEL_DEPLOYMENT_NAME (default `gpt-image-2`). The generated PNG is stored with
generated_files.store_file (blob SAS link) and returned as markdown for the model to include verbatim.
"""

import base64
import os
import re
from typing import Annotated
from urllib.parse import urlparse

from agent_framework import AgentContext, AgentMiddleware, Content, tool

from shared.generated_files import store_file

SIZES = ("1024x1024", "1536x1024", "1024x1536")
QUALITIES = ("low", "medium", "high", "auto")


def image_base_url(project_endpoint: str) -> str:
    parsed = urlparse(project_endpoint)
    return f"{parsed.scheme}://{parsed.netloc}/openai/v1/"


async def generate_png(prompt: str, size: str, quality: str) -> bytes:
    from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
    from openai import AsyncOpenAI

    async with DefaultAzureCredential() as credential:
        provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
        client = AsyncOpenAI(base_url=image_base_url(os.environ["IMAGE_PROJECT_ENDPOINT"]), api_key=provider)
        try:
            result = await client.images.generate(
                model=os.environ.get("IMAGE_MODEL_DEPLOYMENT_NAME", "gpt-image-2"),
                prompt=prompt,
                size=size,
                quality=quality,
                n=1,
            )
        finally:
            await client.close()
    return base64.b64decode(result.data[0].b64_json)


@tool
async def generate_image(
    prompt: Annotated[str, "Detailed description of the image to create."],
    size: Annotated[str, "square=1024x1024, landscape=1536x1024, portrait=1024x1536."] = "1024x1024",
    quality: Annotated[str, "low, medium, high or auto."] = "auto",
) -> str:
    """Generate an image and return a markdown image link to include verbatim in the reply."""
    if size not in SIZES:
        size = "1024x1024"
    if quality not in QUALITIES:
        quality = "auto"
    try:
        data = await generate_png(prompt, size, quality)
    except Exception as exc:
        return f"Image generation failed ({type(exc).__name__}). Tell the user it could not be generated."
    return await store_file(data, "image.png")


_IMAGE_MD = re.compile(r"!\[[^\]]*\]\(https?://[^)\s]+\)")


def _tool_images(contents) -> list[str]:
    found = []
    for content in contents or []:
        if getattr(content, "type", None) == "function_result":
            found += _IMAGE_MD.findall(str(getattr(content, "result", "") or ""))
    return found


class ToolImagesMiddleware(AgentMiddleware):
    """Append images returned by tools to the reply, since the model often omits the link."""

    async def process(self, context: AgentContext, call_next) -> None:
        await call_next()
        result = context.result
        if result is None:
            return
        pending: list[str] = []
        if context.stream:

            def hook(update):
                pending.extend(i for i in _tool_images(update.contents) if i not in pending)
                if pending and any(getattr(c, "type", None) == "text" for c in update.contents or []):
                    update.contents.append(Content.from_text("\n\n" + "\n\n".join(pending) + "\n\n"))
                    pending.clear()
                return update

            result.with_transform_hook(hook)
            return
        images = []
        for message in result.messages:
            images += _tool_images(message.contents)
        text = "".join(getattr(m, "text", "") or "" for m in result.messages)
        missing = [i for i in dict.fromkeys(images) if i not in text]
        if missing:
            result.messages[-1].contents.append(Content.from_text("\n\n" + "\n\n".join(missing)))
