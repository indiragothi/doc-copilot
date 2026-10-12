from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from supabase_auth.errors import AuthApiError, AuthInvalidJwtError

from app.api import me
from app.auth import dependencies

USER_ID = "5f0c1b7e-3a52-4c1e-9a43-0d6f4f3b8a11"

app = FastAPI()
app.include_router(me.router)
client = TestClient(app, raise_server_exceptions=False)


def stub_supabase(monkeypatch, get_user):
    async def fake_create_user_client(token: str):
        return SimpleNamespace(auth=SimpleNamespace(get_user=get_user))

    monkeypatch.setattr(dependencies, "create_user_client", fake_create_user_client)


def auth_header(token: str = "token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_missing_token_is_401():
    response = client.get("/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_non_bearer_scheme_is_401():
    response = client.get("/me", headers={"Authorization": "Basic abc"})

    assert response.status_code == 401


def test_valid_token_returns_user(monkeypatch):
    async def get_user(token):
        assert token == "good"
        user = SimpleNamespace(id=USER_ID, email="analyst@example.com")
        return SimpleNamespace(user=user)

    stub_supabase(monkeypatch, get_user)

    response = client.get("/me", headers=auth_header("good"))

    assert response.status_code == 200
    assert response.json() == {"id": USER_ID, "email": "analyst@example.com"}


@pytest.mark.parametrize(
    "error",
    [
        AuthInvalidJwtError("bad jwt"),
        AuthApiError("expired", 401, "bad_jwt"),
    ],
)
def test_rejected_token_is_401(monkeypatch, error):
    async def get_user(token):
        raise error

    stub_supabase(monkeypatch, get_user)

    response = client.get("/me", headers=auth_header())

    assert response.status_code == 401


def test_empty_supabase_response_is_401(monkeypatch):
    async def get_user(token):
        return None

    stub_supabase(monkeypatch, get_user)

    assert client.get("/me", headers=auth_header()).status_code == 401


def test_supabase_outage_is_not_reported_as_401(monkeypatch):
    async def get_user(token):
        raise AuthApiError("upstream down", 503, None)

    stub_supabase(monkeypatch, get_user)

    assert client.get("/me", headers=auth_header()).status_code == 500
