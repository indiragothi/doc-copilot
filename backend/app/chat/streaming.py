import json
import re
from collections.abc import AsyncIterator, Iterable
from typing import Any
from uuid import uuid4

# Tells the AI SDK client to parse the body as a UI message stream.
STREAM_HEADERS = {
    "x-vercel-ai-ui-message-stream": "v1",
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}

WORD = re.compile(r"\S+\s*")


def sse(event: dict[str, Any] | str) -> str:
    data = event if isinstance(event, str) else json.dumps(event, separators=(",", ":"))
    return f"data: {data}\n\n"


async def word_deltas(text: str) -> AsyncIterator[str]:
    """Split a finished answer into small deltas, keeping whitespace and newlines."""
    for match in WORD.finditer(text):
        yield match.group()


async def ui_message_stream(
    deltas: AsyncIterator[str],
    *,
    message_id: str | None = None,
    data_parts: Iterable[dict[str, Any]] = (),
) -> AsyncIterator[dict[str, Any] | str]:
    """Yield AI SDK UI message stream events; callers frame them with `sse`.

    `data_parts` (e.g. citations) are sent after the text, before the stream finishes.
    """
    text_id = uuid4().hex
    yield {"type": "start", "messageId": message_id or uuid4().hex}
    yield {"type": "text-start", "id": text_id}
    async for delta in deltas:
        yield {"type": "text-delta", "id": text_id, "delta": delta}
    yield {"type": "text-end", "id": text_id}
    for part in data_parts:
        yield part
    yield {"type": "finish"}
    yield "[DONE]"
