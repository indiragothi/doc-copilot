from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.auth.dependencies import CurrentUser, get_current_user
from app.chat.messages import (
    UIMessage,
    message_text,
    row_to_ui_message,
    text_parts,
    title_from,
)
from app.chat.orchestrator import stub_reply
from app.chat.streaming import STREAM_HEADERS, TEXT_END, sse, ui_message_stream
from app.database import chats
from app.database.supabase import create_admin_client, create_user_client

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
async def stream(body: StreamRequest, user: CurrentUserDep) -> StreamingResponse:
    # Authorize before streaming starts so failures are plain HTTP errors.
    thread = await owned_thread(body.thread_id, user)
    if not body.messages or body.messages[-1].role != "user":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Last message must be from the user"
        )
    # Only the newest user message is trusted; stored history stays authoritative.
    user_message = body.messages[-1]
    client = await create_user_client(user.access_token)

    async def run_turn() -> AsyncIterator[str]:
        reply: list[str] = []

        async def deltas() -> AsyncIterator[str]:
            async for delta in stub_reply():
                reply.append(delta)
                yield delta

        async for event in ui_message_stream(deltas()):
            yield sse(event)
            # Persist once the answer is complete, before the stream closes.
            if isinstance(event, dict) and event["type"] == TEXT_END:
                answer = "".join(reply).strip()
                user_text = message_text(user_message)
                await chats.save_turn(
                    client,
                    body.thread_id,
                    user_text,
                    user_message.parts,
                    answer,
                    text_parts(answer),
                    title_from(user_text) if thread["title"] is None else None,
                )

    return StreamingResponse(
        run_turn(), media_type="text/event-stream", headers=STREAM_HEADERS
    )
