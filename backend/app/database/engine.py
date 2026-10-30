from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import settings


def create_engine() -> AsyncEngine:
    """Direct Postgres connection for queries Supabase's REST client can't express (pgvector, ts_rank)."""
    url = make_url(settings.database_url).set(drivername="postgresql+psycopg")
    # pre_ping: Supabase and the network drop idle connections; without it the next query on a
    # dead pooled connection fails with "server closed the connection unexpectedly".
    return create_async_engine(url, pool_size=5, pool_pre_ping=True)
