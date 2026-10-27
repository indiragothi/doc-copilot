import asyncio
import json

from app.chat.streaming import (
    answer_events,
    error_events,
    sse,
    start_event,
    status_part,
    word_deltas,
)


async def collect(texts, data_parts=()):
    async def deltas():
        for text in texts:
            yield text

    return [event async for event in answer_events(deltas(), data_parts)]


def test_event_sequence():
    events = asyncio.run(collect(["a", "b"]))

    assert [e["type"] for e in events[:-1]] == [
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


def test_data_parts_follow_text():
    events = asyncio.run(collect(["a"], [{"type": "data-citation", "id": "1"}]))

    assert [e["type"] for e in events[:-1]] == [
        "text-start",
        "text-delta",
        "text-end",
        "data-citation",
        "finish",
    ]


def test_start_event_uses_the_given_message_id():
    assert start_event("m-1") == {"type": "start", "messageId": "m-1"}
    assert start_event()["messageId"]


def test_status_part_is_transient():
    part = status_part({"id": "step-1", "state": "running"})

    assert part["type"] == "data-status"
    assert part["transient"] is True


def test_error_events_end_the_stream():
    assert error_events("boom") == [{"type": "error", "errorText": "boom"}, "[DONE]"]


def test_word_deltas_preserve_text_exactly():
    text = "First line [1].\n\n- item two\n"

    async def collect_words():
        return [delta async for delta in word_deltas(text)]

    assert "".join(asyncio.run(collect_words())) == text
