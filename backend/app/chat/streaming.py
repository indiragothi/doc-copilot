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
DONE = "[DONE]"


def sse(event: dict[str, Any] | str) -> str:
    data = event if isinstance(event, str) else json.dumps(event, separators=(",", ":"))
    return f"data: {data}\n\n"


async def word_deltas(text: str) -> AsyncIterator[str]:
    """Split a finished answer into small deltas, keeping whitespace and newlines."""
    for match in WORD.finditer(text):
        yield match.group()


def start_event(message_id: str | None = None) -> dict[str, Any]:
    return {"type": "start", "messageId": message_id or uuid4().hex}


def status_part(step: dict[str, Any]) -> dict[str, Any]:
    """Live progress for the UI. Transient: shown while waiting, never stored in the message."""
    return {"type": "data-status", "data": step, "transient": True}


def error_events(message: str) -> list[dict[str, Any] | str]:
    return [{"type": "error", "errorText": message}, DONE]


async def answer_events(
    deltas: AsyncIterator[str], data_parts: Iterable[dict[str, Any]] = ()
) -> AsyncIterator[dict[str, Any] | str]:
    """The verified answer, then its `data_parts` (e.g. citations), then the end of the stream."""
    text_id = uuid4().hex
    yield {"type": "text-start", "id": text_id}
    async for delta in deltas:
        yield {"type": "text-delta", "id": text_id, "delta": delta}
    yield {"type": "text-end", "id": text_id}
    for part in data_parts:
        yield part
    yield {"type": "finish"}
    yield DONE
