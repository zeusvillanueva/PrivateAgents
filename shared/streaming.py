"""Work around the hosted agent server dropping tool results when streaming.

The server's streaming converter groups updates by `message_id` and only starts a new group when both ids are
set and different. Updates produced by the function-invocation loop (function_result, and the text that follows)
have no message_id, so they are swallowed into the preceding function_call group and never emitted: the client
sees only the tool call and no reply. This middleware gives each run of same-kind updates its own message_id.
"""

from __future__ import annotations

from agent_framework import AgentContext, AgentMiddleware

_KINDS = ("function_call", "function_result", "text")


def _kind(update) -> str | None:
    for content in update.contents or []:
        if content.type in _KINDS:
            return content.type
    return None


class StreamMessageIdMiddleware(AgentMiddleware):
    async def process(self, context: AgentContext, call_next) -> None:
        await call_next()
        result = context.result
        if result is None or not context.stream:
            return

        state = {"n": 0, "kind": None, "orig": None}

        def hook(update):
            kind, orig = _kind(update), update.message_id
            if kind is None:
                return update
            if kind != state["kind"] or (orig and state["orig"] and orig != state["orig"]):
                state["n"] += 1
            state["kind"], state["orig"] = kind, orig or state["orig"]
            update.message_id = f"msg_{state['n']}"
            return update

        result.with_transform_hook(hook)
