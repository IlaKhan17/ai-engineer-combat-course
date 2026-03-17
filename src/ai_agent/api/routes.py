from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid
import asyncio

from src.ai_agent.services.enricher import CompanyEnricher

router = APIRouter(prefix="/api/v1", tags=["Companies"])

# ── In-Memory Store (replaces DB for now) ────────────────────────────────────
# This is a dict that acts like a database
# Key = job_id, Value = job status + results
jobs: dict[str, dict] = {}


# ── Request/Response Models ───────────────────────────────────────────────────
class EnrichRequest(BaseModel):
    companies: list[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="List of company names to enrich"
    )

class JobStatus(BaseModel):
    job_id: str
    status: str                          # pending, running, completed, failed
    created_at: datetime
    completed_at: Optional[datetime] = None
    total: int = 0
    successful: int = 0
    failed: int = 0
    results: list[dict] = []
    failures: list[str] = []


# ── Background Task ───────────────────────────────────────────────────────────
async def run_enrichment_job(job_id: str, company_names: list[str]):
    """
    This runs AFTER the HTTP response is sent.
    Client gets job_id instantly, then polls for results.
    """
    jobs[job_id]["status"] = "running"

    enricher = CompanyEnricher(max_retries=3)
    profiles, failures = await enricher.enrich_companies(company_names)

    # Update job with results
    jobs[job_id].update({
        "status": "completed",
        "completed_at": datetime.utcnow(),
        "total": len(company_names),
        "successful": len(profiles),
        "failed": len(failures),
        "results": [p.model_dump() for p in profiles],
        "failures": failures
    })


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("/enrich", response_model=JobStatus, status_code=202)
async def enrich_companies(
    request: EnrichRequest,
    background_tasks: BackgroundTasks
):
    """
    Start an enrichment job.
    Returns job_id immediately (202 Accepted).
    Client polls GET /jobs/{job_id} for results.
    """
    job_id = str(uuid.uuid4())[:8]  # short readable ID

    # Create job record
    jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "created_at": datetime.utcnow(),
        "completed_at": None,
        "total": len(request.companies),
        "successful": 0,
        "failed": 0,
        "results": [],
        "failures": []
    }

    # Start enrichment WITHOUT blocking the response
    background_tasks.add_task(
        run_enrichment_job,
        job_id,
        request.companies
    )

    return JobStatus(**jobs[job_id])


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """
    Poll this endpoint to check enrichment progress.
    """
    if job_id not in jobs:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found"
        )
    return JobStatus(**jobs[job_id])


@router.get("/jobs", response_model=list[JobStatus])
async def list_all_jobs():
    """
    List all enrichment jobs.
    """
    return [JobStatus(**job) for job in jobs.values()]
