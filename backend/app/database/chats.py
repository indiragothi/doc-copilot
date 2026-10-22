from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from supabase import AsyncClient

Row = dict[str, Any]


async def ensure_user(admin: AsyncClient, user_id: UUID, email: str | None) -> None:
    """Mirror the Supabase auth user into `users`, which chat_threads references."""
    await (
        admin.table("users")
        .upsert({"id": str(user_id), "email": email}, on_conflict="id")
        .execute()
    )


async def get_thread(admin: AsyncClient, thread_id: UUID) -> Row | None:
    """Admin lookup, so a thread owned by someone else is distinguishable from a missing one."""
    response = (
        await admin.table("chat_threads")
        .select("*")
        .eq("id", str(thread_id))
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


async def list_threads(client: AsyncClient) -> list[Row]:
    response = (
        await client.table("chat_threads")
        .select("*")
        .order("updated_at", desc=True)
        .execute()
    )
    return response.data


async def create_thread(client: AsyncClient, user_id: UUID) -> Row:
    response = (
        await client.table("chat_threads").insert({"user_id": str(user_id)}).execute()
    )
    return response.data[0]


async def list_messages(client: AsyncClient, thread_id: UUID) -> list[Row]:
    response = (
        await client.table("chat_messages")
        .select("*")
        .eq("thread_id", str(thread_id))
        .order("created_at")
        .execute()
    )
    return response.data


async def save_turn(
    client: AsyncClient,
    thread_id: UUID,
    user_text: str,
    user_parts: list[Any],
    assistant_text: str,
    assistant_parts: list[Any],
    title: str | None,
) -> None:
    """Store both sides of a finished turn. `title` is set only for a thread's first turn."""
    thread = str(thread_id)
    # Explicit timestamps keep the user message ordered before the reply.
    user_at = datetime.now(UTC)
    assistant_at = datetime.now(UTC)
    await (
        client.table("chat_messages")
        .insert(
            [
                {
                    "thread_id": thread,
                    "role": "user",
                    "content": user_text,
                    "parts": user_parts,
                    "created_at": user_at.isoformat(),
                },
                {
                    "thread_id": thread,
                    "role": "assistant",
                    "content": assistant_text,
                    "parts": assistant_parts,
                    "created_at": assistant_at.isoformat(),
                },
            ]
        )
        .execute()
    )
    update: Row = {"updated_at": datetime.now(UTC).isoformat()}
    if title is not None:
        update["title"] = title
    await client.table("chat_threads").update(update).eq("id", thread).execute()
