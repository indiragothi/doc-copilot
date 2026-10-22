import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

# Tells the AI SDK client to parse the body as a UI message stream.
STREAM_HEADERS = {
    "x-vercel-ai-ui-message-stream": "v1",
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}

TEXT_END = "text-end"


def sse(event: dict[str, Any] | str) -> str:
    data = event if isinstance(event, str) else json.dumps(event, separators=(",", ":"))
    return f"data: {data}\n\n"


async def ui_message_stream(
    deltas: AsyncIterator[str],
) -> AsyncIterator[dict[str, Any] | str]:
    """Yield AI SDK UI message stream events; callers frame them with `sse`."""
    text_id = uuid4().hex
    yield {"type": "start", "messageId": uuid4().hex}
    yield {"type": "text-start", "id": text_id}
    async for delta in deltas:
        yield {"type": "text-delta", "id": text_id, "delta": delta}
    yield {"type": TEXT_END, "id": text_id}
    yield {"type": "finish"}
    yield "[DONE]"
