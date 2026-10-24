from app.chat.messages import (
    UIMessage,
    message_text,
    row_to_ui_message,
    title_from,
)


def test_message_text_joins_text_parts_only():
    message = UIMessage(
        role="user",
        parts=[
            {"type": "text", "text": "Apple "},
            {"type": "file", "url": "x"},
            {"type": "text", "text": "revenue"},
        ],
    )

    assert message_text(message) == "Apple revenue"


def test_row_uses_stored_parts():
    parts = [{"type": "text", "text": "hi"}]
    row = {"id": "1", "role": "assistant", "content": "hi", "parts": parts}

    assert row_to_ui_message(row) == {"id": "1", "role": "assistant", "parts": parts}


def test_row_without_parts_falls_back_to_content():
    row = {"id": "1", "role": "user", "content": "hello", "parts": None}

    assert row_to_ui_message(row)["parts"] == [{"type": "text", "text": "hello"}]


def test_title_collapses_whitespace_and_truncates():
    assert title_from("  what   is\nrevenue ") == "what is revenue"
    long = title_from("word " * 40)
    assert len(long) == 60
    assert long.endswith("…")


def citation():
    from datetime import date
    from uuid import uuid4

    from app.assistant.outputs import VerifiedCitation

    return VerifiedCitation(
        marker=1,
        chunk_id=uuid4(),
        quote="q",
        excerpt="e",
        ticker="AAPL",
        form_type="10-K",
        fiscal_year=2025,
        filing_date=date(2025, 10, 31),
        section="Item 7.",
        page=None,
    )


def test_assistant_parts_append_citation_data_parts_after_text():
    from app.chat.messages import assistant_parts

    cited = citation()

    parts = assistant_parts("Answer [1].", [cited])

    assert parts[0] == {"type": "text", "text": "Answer [1]."}
    assert parts[1]["type"] == "data-citation"
    assert parts[1]["id"] == "1"
    assert parts[1]["data"]["chunk_id"] == str(cited.chunk_id)
    assert parts[1]["data"]["filing_date"] == "2025-10-31"


def test_history_for_model_uses_text_and_drops_citation_parts():
    from pydantic_ai.messages import ModelRequest, ModelResponse

    from app.chat.messages import history_for_model

    rows = [
        {"role": "user", "content": "q1", "parts": None},
        {
            "role": "assistant",
            "content": "a1 [1]",
            "parts": [{"type": "data-citation"}],
        },
    ]

    history = history_for_model(rows)

    assert isinstance(history[0], ModelRequest)
    assert history[0].parts[0].content == "q1"
    assert isinstance(history[1], ModelResponse)
    assert history[1].parts[0].content == "a1 [1]"


def test_history_for_model_keeps_only_recent_messages():
    from app.chat.messages import HISTORY_MESSAGE_LIMIT, history_for_model

    rows = [{"role": "user", "content": str(i), "parts": None} for i in range(30)]

    history = history_for_model(rows)

    assert len(history) == HISTORY_MESSAGE_LIMIT
    assert history[-1].parts[0].content == "29"
