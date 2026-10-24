from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from app.assistant.outputs import VerifiedCitation

TITLE_MAX_CHARS = 60
# Earlier turns given to the model for follow-up questions; bounds prompt size.
HISTORY_MESSAGE_LIMIT = 10


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


def citation_part(citation: VerifiedCitation) -> dict[str, Any]:
    """AI SDK data part carrying everything the UI needs to render a citation."""
    return {
        "type": "data-citation",
        "id": str(citation.marker),
        "data": citation.model_dump(mode="json"),
    }


def assistant_parts(
    text: str, citations: list[VerifiedCitation]
) -> list[dict[str, Any]]:
    return [*text_parts(text), *(citation_part(citation) for citation in citations)]


def row_to_ui_message(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "role": row["role"],
        "parts": row["parts"] or text_parts(row["content"]),
    }


def history_for_model(rows: list[dict[str, Any]]) -> list[ModelMessage]:
    """Recent stored messages as plain text; citation parts are left out."""
    history: list[ModelMessage] = []
    for row in rows[-HISTORY_MESSAGE_LIMIT:]:
        if row["role"] == "user":
            history.append(ModelRequest(parts=[UserPromptPart(row["content"])]))
        else:
            history.append(ModelResponse(parts=[TextPart(row["content"])]))
    return history


def title_from(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= TITLE_MAX_CHARS:
        return collapsed
    return collapsed[: TITLE_MAX_CHARS - 1].rstrip() + "…"
