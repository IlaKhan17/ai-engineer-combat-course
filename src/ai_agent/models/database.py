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
    if not database_url.startswith("postgresql+asyncpg://"):
        return database_url, {}

    parsed = urlparse(database_url)
    query = parse_qs(parsed.query, keep_blank_values=True)

    connect_args: dict = {}
    if "sslmode" in query:
        connect_args["ssl"] = True
        query.pop("sslmode", None)

    query.pop("channel_binding", None)

    new_query = urlencode(query, doseq=True)
    normalized_url = urlunparse(parsed._replace(query=new_query))
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
    echo=settings.debug,       # logs all SQL when debug=True
    pool_size=5,               # max 5 connections open at once
    max_overflow=10,           # allow 10 extra during traffic spikes
    connect_args=connect_args  # e.g. {"ssl": True} for Neon
)

# Session factory — use this everywhere instead of creating sessions manually
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False     # keep objects usable after commit
)


# ── Dependency for FastAPI ────────────────────────────────────────────────────
async def get_db():
    """
    FastAPI dependency that gives each endpoint its own DB session.
    Automatically commits on success, rolls back on error.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise