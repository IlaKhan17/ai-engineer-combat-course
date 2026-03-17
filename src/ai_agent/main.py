from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import time
import uuid

from src.ai_agent.api.routes import router
from src.ai_agent.config import get_settings

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)
settings = get_settings()


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Starting {settings.app_name}...")
    yield
    logger.info("🛑 Shutting down...")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Production AI Agent API - Day 2",
    lifespan=lifespan
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every request with timing and request ID."""
    request_id = str(uuid.uuid4())[:8]
    start = time.time()

    logger.info(f"[{request_id}] → {request.method} {request.url.path}")
    response = await call_next(request)
    duration = (time.time() - start) * 1000

    logger.info(f"[{request_id}] ← {response.status_code} ({duration:.1f}ms)")
    response.headers["X-Request-ID"] = request_id
    return response


# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(router)

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "app": settings.app_name,
        "debug": settings.debug
    }