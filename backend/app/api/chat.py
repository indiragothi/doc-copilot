import asyncio
from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from openai import APIError
from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.exceptions import ModelHTTPError

from app.assistant.progress import ProgressReporter
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
from app.chat.streaming import (
    STREAM_HEADERS,
    answer_events,
    error_events,
    sse,
    start_event,
    status_part,
    word_deltas,
)
from app.database import chats
from app.database.supabase import create_admin_client, create_user_client
from app.retrieval.retriever import DocumentRetriever

log = structlog.get_logger()

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


def model_failure_message(error: Exception) -> str:
    if getattr(error, "status_code", None) == 429:
        return (
            "The model's usage limit was reached. Please wait a minute and try again."
        )
    return "The model service failed. Please try again."


@router.get("/threads")
async def list_threads(user: CurrentUserDep) -> list[ThreadResponse]:
    client = await create_user_client(user.access_token)
    return [ThreadResponse(**row) for row in await chats.list_threads(client)]


@router.post("/threads", status_code=status.HTTP_201_CREATED)
async def create_thread(user: CurrentUserDep) -> ThreadResponse:
    await chats.ensure_user(await create_admin_client(), user.id, user.email)
    client = await create_user_client(user.access_token)
    return ThreadResponse(**await chats.create_thread(client, user.id))


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(thread_id: UUID, user: CurrentUserDep) -> None:
    await owned_thread(thread_id, user)
    client = await create_user_client(user.access_token)
    await chats.delete_thread(client, thread_id)


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

    async def events() -> AsyncIterator[str]:
        yield sse(start_event())
        # The answer is verified in full before any of it is streamed. Meanwhile the
        # analyst gets live status steps from the agent.
        steps: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        turn = asyncio.create_task(
            run_turn(
                DocumentRetriever(request.app.state.engine),
                user_id=user.id,
                thread_id=body.thread_id,
                question=user_text,
                history=history_for_model(
                    await chats.list_messages(client, body.thread_id)
                ),
                progress=ProgressReporter(steps.put_nowait),
            )
        )
        turn.add_done_callback(lambda _: steps.put_nowait(None))
        try:
            while (step := await steps.get()) is not None:
                yield sse(status_part(step))
            answer = await turn
        except (ModelHTTPError, APIError) as error:
            log.warning("model_service_failed", thread_id=str(body.thread_id))
            for event in error_events(model_failure_message(error)):
                yield sse(event)
            return
        finally:
            # Also runs when the client disconnects: stop spending model quota.
            turn.cancel()

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
        async for event in answer_events(
            word_deltas(answer.text),
            [citation_part(citation) for citation in answer.citations],
        ):
            yield sse(event)

    return StreamingResponse(
        events(), media_type="text/event-stream", headers=STREAM_HEADERS
    )
