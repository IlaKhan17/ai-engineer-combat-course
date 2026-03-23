from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import AsyncEngine
from alembic import context
import asyncio
import sys
import os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.ai_agent.models.database import Base
from src.ai_agent.config import get_settings

settings = get_settings()
config = context.config

def _normalize_asyncpg_url_for_sqlalchemy(database_url: str) -> tuple[str, dict]:
    """
    SQLAlchemy's asyncpg dialect passes URL query parameters as kwargs to
    asyncpg.connect(). Neon URLs often include `sslmode` / `channel_binding`,
    but asyncpg.connect() doesn't accept `sslmode` as a kwarg.
    """
    if not database_url.startswith("postgresql+asyncpg://"):
        return database_url, {}

    parsed = urlparse(database_url)
    query = parse_qs(parsed.query, keep_blank_values=True)

    connect_args: dict = {}
    if "sslmode" in query:
        # asyncpg expects `ssl` (bool or SSLContext), not `sslmode`.
        connect_args["ssl"] = True
        query.pop("sslmode", None)

    # Neon sometimes includes channel binding params; asyncpg doesn't accept
    # them as kwargs, so strip them.
    query.pop("channel_binding", None)

    new_query = urlencode(query, doseq=True)
    normalized_url = urlunparse(parsed._replace(query=new_query))
    return normalized_url, connect_args


normalized_url, connect_args = _normalize_asyncpg_url_for_sqlalchemy(
    settings.database_url
)

# Set database URL from our settings (normalized for asyncpg)
config.set_main_option("sqlalchemy.url", normalized_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine
    connectable = create_async_engine(normalized_url, connect_args=connect_args)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
