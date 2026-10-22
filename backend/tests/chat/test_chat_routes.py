from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import chat
from app.auth.dependencies import CurrentUser, get_current_user

USER_ID = UUID("5f0c1b7e-3a52-4c1e-9a43-0d6f4f3b8a11")
OTHER_ID = UUID("9a1d2c3e-1111-4222-8333-444455556666")
THREAD_ID = "0b7a5c1e-2f3d-4a5b-8c9d-1e2f3a4b5c6d"

app = FastAPI()
app.include_router(chat.router)
app.dependency_overrides[get_current_user] = lambda: CurrentUser(
    id=USER_ID, email="analyst@example.com", access_token="token"
)
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def fake_db(monkeypatch):
    state = {"thread_owner": USER_ID, "title": None, "saved": [], "messages": []}

    async def client_factory(*_):
        return object()

    async def get_thread(_, thread_id):
        if str(thread_id) != THREAD_ID:
            return None
        return {
            "id": THREAD_ID,
            "user_id": str(state["thread_owner"]),
            "title": state["title"],
        }

    async def save_turn(*args):
        state["saved"].append(args[1:])

    async def list_messages(_, __):
        return state["messages"]

    monkeypatch.setattr(chat, "create_admin_client", client_factory)
    monkeypatch.setattr(chat, "create_user_client", client_factory)
    monkeypatch.setattr(chat.chats, "get_thread", get_thread)
    monkeypatch.setattr(chat.chats, "save_turn", save_turn)
    monkeypatch.setattr(chat.chats, "list_messages", list_messages)
    return state


def stream_body(thread_id=THREAD_ID, role="user"):
    message = {"id": "m1", "role": role, "parts": [{"type": "text", "text": "Hello?"}]}
    return {"threadId": thread_id, "messages": [message]}


def test_stream_emits_events_and_persists_turn(fake_db):
    response = client.post("/chat/stream", json=stream_body())

    assert response.status_code == 200
    assert response.headers["x-vercel-ai-ui-message-stream"] == "v1"
    assert response.text.rstrip().endswith("data: [DONE]")
    assert '"type":"text-delta"' in response.text
    [(thread_id, user_text, _, answer, answer_parts, title)] = fake_db["saved"]
    assert str(thread_id) == THREAD_ID
    assert user_text == "Hello?"
    assert answer.startswith("This is a stubbed response.")
    assert answer_parts == [{"type": "text", "text": answer}]
    assert title == "Hello?"


def test_title_not_overwritten_after_first_turn(fake_db):
    fake_db["title"] = "Existing"

    client.post("/chat/stream", json=stream_body())

    assert fake_db["saved"][0][-1] is None


def test_other_users_thread_is_403_and_nothing_saved(fake_db):
    fake_db["thread_owner"] = OTHER_ID

    response = client.post("/chat/stream", json=stream_body())

    assert response.status_code == 403
    assert fake_db["saved"] == []


def test_missing_thread_is_404():
    other = "11111111-2222-4333-8444-555555555555"

    assert client.post("/chat/stream", json=stream_body(other)).status_code == 404


def test_last_message_must_be_from_user():
    response = client.post("/chat/stream", json=stream_body(role="assistant"))

    assert response.status_code == 422


def test_history_for_other_users_thread_is_403(fake_db):
    fake_db["thread_owner"] = OTHER_ID

    assert client.get(f"/chat/threads/{THREAD_ID}/messages").status_code == 403


def test_history_returns_ui_messages(fake_db):
    fake_db["messages"] = [
        {"id": "1", "role": "user", "content": "hi", "parts": None},
        {
            "id": "2",
            "role": "assistant",
            "content": "yo",
            "parts": [{"type": "text", "text": "yo"}],
        },
    ]

    response = client.get(f"/chat/threads/{THREAD_ID}/messages")

    assert response.status_code == 200
    assert [m["role"] for m in response.json()] == ["user", "assistant"]
    assert response.json()[0]["parts"] == [{"type": "text", "text": "hi"}]


def test_chat_routes_require_auth():
    bare = TestClient(FastAPI(routes=chat.router.routes), raise_server_exceptions=False)

    assert bare.get("/chat/threads").status_code == 401
    assert bare.post("/chat/stream", json=stream_body()).status_code == 401
