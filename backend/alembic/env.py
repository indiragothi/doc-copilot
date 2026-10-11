from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from alembic import context
from app.config import settings
from app.database.models import Base

target_metadata = Base.metadata

# Supabase gives a plain `postgresql://` URL; SQLAlchemy needs the psycopg 3 driver named.
# Built here rather than in alembic.ini, where `%` in an encoded password breaks interpolation.
url = make_url(settings.database_url).set(drivername="postgresql+psycopg")


def run_migrations_offline() -> None:
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
