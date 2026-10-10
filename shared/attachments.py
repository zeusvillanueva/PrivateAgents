"""Attachment contract between the chat app and the hosted agents.

The chat app uploads files to Foundry itself and prepends a block to the user message:

    <attachments>{"vector_store_ids": ["vs_..."], "file_ids": ["file_..."]}</attachments>

The middleware strips the block and exposes the IDs so each agent can attach the right tools per request.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from agent_framework import AgentContext, AgentMiddleware

_BLOCK = re.compile(r"<attachments>(.*?)</attachments>\s*", re.DOTALL)
_ID = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")


@dataclass
class Attachments:
    vector_store_ids: list[str] = field(default_factory=list)
    file_ids: list[str] = field(default_factory=list)


def _clean(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [v for v in values if isinstance(v, str) and _ID.match(v)]


def parse_attachments(text: str) -> tuple[str, Attachments]:
    """Return (text without attachment blocks, merged attachments)."""
    found = Attachments()
    for raw in _BLOCK.findall(text):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            found.vector_store_ids += _clean(data.get("vector_store_ids"))
            found.file_ids += _clean(data.get("file_ids"))
    return _BLOCK.sub("", text).strip(), found


class AttachmentToolsMiddleware(AgentMiddleware):
    """Builds per-request tools from attachments found in the latest user message."""

    def __init__(self, build_tools: Callable[[Attachments], list[Any]]):
        self._build_tools = build_tools

    async def process(self, context: AgentContext, call_next) -> None:
        attachments = Attachments()
        for message in reversed(context.messages):
            if getattr(message, "role", None) != "user":
                continue
            for content in getattr(message, "contents", []) or []:
                text = getattr(content, "text", None)
                if text and "<attachments>" in text:
                    content.text, found = parse_attachments(text)
                    attachments.vector_store_ids += found.vector_store_ids
                    attachments.file_ids += found.file_ids
            break
        tools = self._build_tools(attachments)
        if tools:
            options = dict(context.options or {})
            options["tools"] = [*(options.get("tools") or []), *tools]
            context.options = options
        await call_next()
