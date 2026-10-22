from typing import Any

from pydantic import BaseModel, ConfigDict

TITLE_MAX_CHARS = 60


class UIMessage(BaseModel):
    """AI SDK UI message as sent by the browser. Only text parts matter for now."""

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    role: str
    parts: list[dict[str, Any]]


def message_text(message: UIMessage) -> str:
    return "".join(
        part.get("text", "") for part in message.parts if part.get("type") == "text"
    )


def text_parts(text: str) -> list[dict[str, str]]:
    return [{"type": "text", "text": text}]


def row_to_ui_message(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "role": row["role"],
        "parts": row["parts"] or text_parts(row["content"]),
    }


def title_from(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= TITLE_MAX_CHARS:
        return collapsed
    return collapsed[: TITLE_MAX_CHARS - 1].rstrip() + "…"
