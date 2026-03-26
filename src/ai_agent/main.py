from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import time
import uuid
import sys
from pathlib import Path

# Make `python main.py` work even when run from inside `src/ai_agent/`
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
    # Keep logs ASCII-only for Windows consoles (cp1252).
    logger.info(f"Starting {settings.app_name}...")

    # Dev helper: create tables if they don't exist yet.
    # This prevents 500s like `relation "company_jobs" does not exist`.
    if settings.debug:
        from src.ai_agent.models.database import init_db
        await init_db()

    yield
    logger.info("Shutting down...")


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

    # Keep log prefix ASCII-only so Windows consoles don't choke.
    logger.info(f"[{request_id}] -> {request.method} {request.url.path}")
    response = await call_next(request)
    duration = (time.time() - start) * 1000

    logger.info(f"[{request_id}] <- {response.status_code} ({duration:.1f}ms)")

    # Log response body (truncated) to make debugging easier.
    # This is safe for normal JSON responses; streaming responses may not have .body.
    try:
        body = getattr(response, "body", None)
        if body:
            body_preview_max = 2000
            body_text = body.decode("utf-8", errors="replace")
            if len(body_text) > body_preview_max:
                body_text = body_text[:body_preview_max] + "...(truncated)"
            logger.info(f"[{request_id}] body: {body_text}")
            # Also print to stdout so it shows up reliably in uvicorn logs.
            print(f"[{request_id}] body: {body_text}")
    except Exception:
        # Never fail the request just because logging failed.
        pass

    response.headers["X-Request-ID"] = request_id
    return response

from fastapi.responses import JSONResponse
import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    error_detail = traceback.format_exc()
    logger.error(f"💥 Unhandled error:\n{error_detail}")
    return JSONResponse(
        status_code=500,
        content={
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": error_detail
        }
    )
# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(router)

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "app": settings.app_name,
        "debug": settings.debug
    }