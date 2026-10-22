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
