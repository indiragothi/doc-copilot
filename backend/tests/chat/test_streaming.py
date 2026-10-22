import asyncio
import json

from app.chat.streaming import sse, ui_message_stream


async def collect(texts):
    async def deltas():
        for text in texts:
            yield text

    return [event async for event in ui_message_stream(deltas())]


def test_event_sequence():
    events = asyncio.run(collect(["a", "b"]))

    assert [e["type"] for e in events[:-1]] == [
        "start",
        "text-start",
        "text-delta",
        "text-delta",
        "text-end",
        "finish",
    ]
    assert events[-1] == "[DONE]"
    assert [e["delta"] for e in events[:-1] if e["type"] == "text-delta"] == ["a", "b"]
    assert len({e["id"] for e in events[:-1] if e["type"].startswith("text-")}) == 1


def test_sse_framing():
    assert sse("[DONE]") == "data: [DONE]\n\n"
    framed = sse({"type": "finish"})
    assert framed.startswith("data: ") and framed.endswith("\n\n")
    assert json.loads(framed[6:]) == {"type": "finish"}
