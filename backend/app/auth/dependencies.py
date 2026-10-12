from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase_auth.errors import AuthApiError, AuthInvalidJwtError

from app.database.supabase import create_user_client

# auto_error=False so a missing header yields our 401, not FastAPI's default.
bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    email: str | None
    # Kept so routes can build a user-scoped client (RLS applies) without re-parsing headers.
    access_token: str


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUser:
    """Verify the Supabase access token by asking Supabase Auth who it belongs to."""
    if credentials is None:
        raise _unauthorized("Missing bearer token")

    token = credentials.credentials
    client = await create_user_client(token)
    try:
        response = await client.auth.get_user(token)
    except AuthInvalidJwtError:
        raise _unauthorized("Invalid or expired token") from None
    except AuthApiError as error:
        # 5xx means Supabase itself is failing, not that the token is bad.
        if error.status >= 500:
            raise
        raise _unauthorized("Invalid or expired token") from None

    if response is None or response.user is None:
        raise _unauthorized("Invalid or expired token")

    user = response.user
    return CurrentUser(id=UUID(user.id), email=user.email, access_token=token)
