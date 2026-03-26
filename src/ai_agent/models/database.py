from sqlalchemy import (
    Column, String, Integer, 
    DateTime, Text, JSON
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker
)
from datetime import datetime
from src.ai_agent.config import get_settings
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

settings = get_settings()

def _normalize_asyncpg_url_for_sqlalchemy(database_url: str) -> tuple[str, dict]:
    """
    SQLAlchemy's asyncpg dialect passes URL query params as kwargs into
    `asyncpg.connect(**kwargs)`.

    Neon connection strings commonly include query params like:
      - `sslmode=require`
      - `channel_binding=require`

    asyncpg.connect does NOT accept `sslmode` / `channel_binding` kwargs,
    so we must strip them from the URL query string.
    """
    if not database_url:
        return database_url, {}

    database_url = database_url.strip()
    if not database_url.startswith("postgresql+asyncpg://"):
        return database_url, {}

    parsed = urlparse(database_url)
    query = parsed.query or ""

    keep_parts: list[str] = []
    found_sslmode = False
    found_channel_binding = False

    # Filter query by key while preserving the original value/encoding.
    for part in query.split("&"):
        if not part:
            continue
        key = part.split("=", 1)[0]
        key_lower = key.lower()
        if key_lower == "sslmode":
            found_sslmode = True
            continue
        if key_lower == "channel_binding":
            found_channel_binding = True
            continue
        keep_parts.append(part)

    new_query = "&".join(keep_parts)
    normalized_url = urlunparse(parsed._replace(query=new_query))

    connect_args: dict = {}
    if found_sslmode or found_channel_binding:
        # asyncpg expects `ssl` (bool or SSLContext), not `sslmode`.
        connect_args["ssl"] = True

    return normalized_url, connect_args


normalized_url, connect_args = _normalize_asyncpg_url_for_sqlalchemy(
    settings.database_url
)

# ── Base Class ────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Tables ────────────────────────────────────────────────────────────────────
class CompanyJob(Base):
    """Stores enrichment jobs — replaces our in-memory dict."""
    __tablename__ = "company_jobs"

    job_id      = Column(String, primary_key=True)
    status      = Column(String, default="pending")     # pending/running/completed/failed
    created_at  = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    total       = Column(Integer, default=0)
    successful  = Column(Integer, default=0)
    failed      = Column(Integer, default=0)
    results     = Column(JSON, default=list)            # stores list of company profiles
    failures    = Column(JSON, default=list)            # stores list of failed names


class CompanyMemory(Base):
    """
    Stores enriched company data permanently.
    This is the AI agent's long-term memory.
    Later we add a vector column for semantic search.
    """
    __tablename__ = "company_memory"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    name            = Column(String, unique=True, index=True)
    domain          = Column(String)
    employee_count  = Column(Integer, nullable=True)
    industry        = Column(String, default="Unknown")
    funding_stage   = Column(String, nullable=True)
    enriched_at     = Column(DateTime, default=datetime.utcnow)
    raw_data        = Column(JSON, nullable=True)       # store original API response


# ── Engine + Session ──────────────────────────────────────────────────────────
engine = create_async_engine(
    normalized_url,
    echo=settings.debug,
    connect_args=connect_args,  # e.g. {"ssl": True} for Neon
    pool_pre_ping=True,     # avoid "connection is closed" from stale pooled conns
    pool_recycle=1800,      # recycle connections every 30 minutes (dev-safe)
    pool_size=5,
    max_overflow=10,
)

# Session factory — use this everywhere instead of creating sessions manually
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False     # keep objects usable after commit
)

async def init_db() -> None:
    """
    Dev-friendly DB initialization.

    Ensures tables exist so the API doesn't 500 before you run migrations.
    In production, prefer Alembic migrations over create_all().
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── Dependency for FastAPI ────────────────────────────────────────────────────
async def get_db():
    """
    FastAPI dependency that gives each endpoint its own DB session.

    Do NOT auto-commit here:
    - write operations are committed inside service methods (JobService)
    - read-only endpoints (GET) should not commit
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise