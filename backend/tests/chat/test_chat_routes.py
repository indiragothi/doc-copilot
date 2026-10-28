from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic_ai.exceptions import ModelHTTPError

from app.api import chat
from app.assistant.outputs import VerifiedAnswer, VerifiedCitation
from app.auth.dependencies import CurrentUser, get_current_user

USER_ID = UUID("5f0c1b7e-3a52-4c1e-9a43-0d6f4f3b8a11")
OTHER_ID = UUID("9a1d2c3e-1111-4222-8333-444455556666")
THREAD_ID = "0b7a5c1e-2f3d-4a5b-8c9d-1e2f3a4b5c6d"

CHUNK_ID = UUID("7c9e6679-7425-40de-944b-e07fc1f90ae7")
ANSWER = VerifiedAnswer(
    text="Services grew to $96.2 billion [1].",
    citations=[
        VerifiedCitation(
            marker=1,
            chunk_id=CHUNK_ID,
            quote="Services net sales were $96.2 billion",
            excerpt="Services net sales were $96.2 billion in 2025.",
            ticker="AAPL",
            form_type="10-K",
            fiscal_year=2025,
            filing_date="2025-10-31",
            section="Item 7.",
            page=None,
        )
    ],
)

app = FastAPI()
app.state.engine = object()
app.include_router(chat.router)
app.dependency_overrides[get_current_user] = lambda: CurrentUser(
    id=USER_ID, email="analyst@example.com", access_token="token"
)
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def fake_db(monkeypatch):
    state = {
        "thread_owner": USER_ID,
        "title": None,
        "saved": [],
        "citations": [],
        "messages": [],
        "deleted": [],
        "answer": ANSWER,
        "turn": None,
    }

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
        return "assistant-msg-1"

    async def save_citations(_, message_id, citations):
        state["citations"].append((message_id, citations))

    async def fake_run_turn(retriever, **kwargs):
        state["turn"] = kwargs
        with kwargs["progress"].step("Searching filings", "services") as report:
            report("Found 1 passages")
        if isinstance(state["answer"], Exception):
            raise state["answer"]
        return state["answer"]

    async def list_messages(_, __):
        return state["messages"]

    monkeypatch.setattr(chat, "create_admin_client", client_factory)
    monkeypatch.setattr(chat, "create_user_client", client_factory)
    monkeypatch.setattr(chat.chats, "get_thread", get_thread)
    monkeypatch.setattr(chat.chats, "save_turn", save_turn)
    monkeypatch.setattr(chat.chats, "save_citations", save_citations)
    monkeypatch.setattr(chat, "run_turn", fake_run_turn)

    async def delete_thread(_, thread_id):
        state["deleted"].append(str(thread_id))

    monkeypatch.setattr(chat.chats, "list_messages", list_messages)
    monkeypatch.setattr(chat.chats, "delete_thread", delete_thread)
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
    assert answer == ANSWER.text
    assert answer_parts[0] == {"type": "text", "text": ANSWER.text}
    assert title == "Hello?"
    assert fake_db["turn"]["question"] == "Hello?"
    assert fake_db["turn"]["user_id"] == USER_ID


def test_citations_are_streamed_and_persisted(fake_db):
    response = client.post("/chat/stream", json=stream_body())

    assert '"type":"data-citation"' in response.text
    assert response.text.index("data-citation") > response.text.index("text-end")
    [(_, _, _, _, answer_parts, _)] = fake_db["saved"]
    assert answer_parts[1]["type"] == "data-citation"
    assert answer_parts[1]["data"]["chunk_id"] == str(CHUNK_ID)
    assert fake_db["citations"] == [("assistant-msg-1", ANSWER.citations)]


def test_status_steps_are_streamed_before_the_answer(fake_db):
    response = client.post("/chat/stream", json=stream_body())

    text = response.text
    assert text.count('"type":"data-status"') == 2
    assert '"transient":true' in text
    assert '"state":"running"' in text and '"state":"done"' in text
    assert text.index("data-status") < text.index("text-start")
    assert text.index("text-start") < text.index("data-citation")


def test_model_failure_streams_an_error_and_saves_nothing(fake_db):
    fake_db["answer"] = ModelHTTPError(429, "test-model", "rate limited")

    response = client.post("/chat/stream", json=stream_body())

    assert response.status_code == 200
    assert '"type":"error"' in response.text
    assert "usage limit" in response.text
    assert '"type":"text-start"' not in response.text
    assert response.text.rstrip().endswith("data: [DONE]")
    assert fake_db["saved"] == []
    assert fake_db["citations"] == []


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


def test_delete_own_thread(fake_db):
    response = client.delete(f"/chat/threads/{THREAD_ID}")

    assert response.status_code == 204
    assert fake_db["deleted"] == [THREAD_ID]


def test_delete_other_users_thread_is_403_and_nothing_deleted(fake_db):
    fake_db["thread_owner"] = OTHER_ID

    response = client.delete(f"/chat/threads/{THREAD_ID}")

    assert response.status_code == 403
    assert fake_db["deleted"] == []


def test_delete_missing_thread_is_404():
    other = "11111111-2222-4333-8444-555555555555"

    assert client.delete(f"/chat/threads/{other}").status_code == 404


def test_chat_routes_require_auth():
    bare = TestClient(FastAPI(routes=chat.router.routes), raise_server_exceptions=False)

    assert bare.delete(f"/chat/threads/{THREAD_ID}").status_code == 401
    assert bare.get("/chat/threads").status_code == 401
    assert bare.post("/chat/stream", json=stream_body()).status_code == 401
