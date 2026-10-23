import asyncio
from types import SimpleNamespace

from shared.streaming import StreamMessageIdMiddleware


def _u(kind, message_id=None):
    return SimpleNamespace(contents=[SimpleNamespace(type=kind)], message_id=message_id)


def test_each_kind_gets_its_own_message_id():
    updates = [_u("function_call", "m1"), _u("function_call", "m1"), _u("function_result"), _u("text"), _u("text")]
    hooks = []
    result = SimpleNamespace(with_transform_hook=hooks.append)
    ctx = SimpleNamespace(result=result, stream=True)

    async def call_next():
        pass

    asyncio.run(StreamMessageIdMiddleware().process(ctx, call_next))
    ids = [hooks[0](u).message_id for u in updates]
    assert ids == ["msg_1", "msg_1", "msg_2", "msg_3", "msg_3"]
