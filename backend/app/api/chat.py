from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from openai import APIError
from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.exceptions import ModelHTTPError

from app.auth.dependencies import CurrentUser, get_current_user
from app.chat.messages import (
    UIMessage,
    assistant_parts,
    citation_part,
    history_for_model,
    message_text,
    row_to_ui_message,
    title_from,
)
from app.chat.orchestrator import run_turn
from app.chat.streaming import STREAM_HEADERS, sse, ui_message_stream, word_deltas
from app.database import chats
from app.database.supabase import create_admin_client, create_user_client
from app.retrieval.retriever import DocumentRetriever

router = APIRouter(prefix="/chat")

CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


class ThreadResponse(BaseModel):
    id: UUID
    title: str | None
    created_at: str
    updated_at: str


class StreamRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    thread_id: UUID = Field(alias="threadId")
    messages: list[UIMessage]


async def owned_thread(thread_id: UUID, user: CurrentUser) -> dict[str, Any]:
    thread = await chats.get_thread(await create_admin_client(), thread_id)
    if thread is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thread not found")
    if UUID(thread["user_id"]) != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your thread")
    return thread


@router.get("/threads")
async def list_threads(user: CurrentUserDep) -> list[ThreadResponse]:
    client = await create_user_client(user.access_token)
    return [ThreadResponse(**row) for row in await chats.list_threads(client)]


@router.post("/threads", status_code=status.HTTP_201_CREATED)
async def create_thread(user: CurrentUserDep) -> ThreadResponse:
    await chats.ensure_user(await create_admin_client(), user.id, user.email)
    client = await create_user_client(user.access_token)
    return ThreadResponse(**await chats.create_thread(client, user.id))


@router.get("/threads/{thread_id}/messages")
async def thread_messages(
    thread_id: UUID, user: CurrentUserDep
) -> list[dict[str, Any]]:
    await owned_thread(thread_id, user)
    client = await create_user_client(user.access_token)
    rows = await chats.list_messages(client, thread_id)
    return [row_to_ui_message(row) for row in rows]


@router.post("/stream")
async def stream(
    body: StreamRequest, user: CurrentUserDep, request: Request
) -> StreamingResponse:
    # Authorize before streaming starts so failures are plain HTTP errors.
    thread = await owned_thread(body.thread_id, user)
    if not body.messages or body.messages[-1].role != "user":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Last message must be from the user"
        )
    # Only the newest user message is trusted; stored history stays authoritative.
    user_message = body.messages[-1]
    user_text = message_text(user_message)
    client = await create_user_client(user.access_token)

    # The answer is verified in full before any of it is streamed, so run it first;
    # upstream failures then surface as HTTP errors rather than a broken stream.
    try:
        answer = await run_turn(
            DocumentRetriever(request.app.state.engine),
            user_id=user.id,
            thread_id=body.thread_id,
            question=user_text,
            history=history_for_model(
                await chats.list_messages(client, body.thread_id)
            ),
        )
    except (ModelHTTPError, APIError) as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "The model service failed"
        ) from error

    parts = assistant_parts(answer.text, answer.citations)
    message_id = await chats.save_turn(
        client,
        body.thread_id,
        user_text,
        user_message.parts,
        answer.text,
        parts,
        title_from(user_text) if thread["title"] is None else None,
    )
    await chats.save_citations(
        await create_admin_client(), message_id, answer.citations
    )

    async def events() -> AsyncIterator[str]:
        stream = ui_message_stream(
            word_deltas(answer.text),
            message_id=message_id,
            data_parts=[citation_part(citation) for citation in answer.citations],
        )
        async for event in stream:
            yield sse(event)

    return StreamingResponse(
        events(), media_type="text/event-stream", headers=STREAM_HEADERS
    )
