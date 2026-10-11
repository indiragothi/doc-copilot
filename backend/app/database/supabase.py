from supabase import AsyncClient, AsyncClientOptions, acreate_client

from app.config import settings


async def create_user_client(access_token: str) -> AsyncClient:
    """Client that acts as the signed-in user, so RLS policies apply to every query."""
    options = AsyncClientOptions(headers={"Authorization": f"Bearer {access_token}"})
    return await acreate_client(
        settings.supabase_url, settings.supabase_anon_key, options
    )


async def create_admin_client() -> AsyncClient:
    """Service-role client that bypasses RLS. Backend only, for privileged writes."""
    return await acreate_client(
        settings.supabase_url, settings.supabase_service_role_key
    )
