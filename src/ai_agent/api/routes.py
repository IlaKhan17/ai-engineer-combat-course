from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from typing import Optional, Annotated
from datetime import datetime

from src.ai_agent.services.enricher import CompanyEnricher
from src.ai_agent.services.job_service import JobService
from src.ai_agent.models.database import get_db, CompanyMemory
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Companies"])


# ── Request/Response Models ───────────────────────────────────────────────────
class EnrichRequest(BaseModel):
    companies: list[str] = Field(..., min_length=1, max_length=20)


class JobStatus(BaseModel):
    job_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    total: int = 0
    successful: int = 0
    failed: int = 0
    results: list[dict] = []
    failures: list[str] = []

    # This tells Pydantic to read from SQLAlchemy objects directly
    model_config = {"from_attributes": True}


# ── Background Task ───────────────────────────────────────────────────────────
async def run_enrichment_job(job_id: str, company_names: list[str]):
    """
    Runs after HTTP response is sent.
    Has its OWN database session — cannot use the request's session
    because that closes when the response is sent.
    """
    from src.ai_agent.models.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        service = JobService(session)
        try:
            await service.mark_running(job_id)

            enricher = CompanyEnricher(max_retries=3)
            profiles, failures = await enricher.enrich_companies(company_names)

            # Save results to jobs table
            await service.complete_job(job_id, profiles, failures)

            # Save companies to long-term memory
            if profiles:
                await service.save_companies(profiles)

        except Exception as e:
            await service.fail_job(job_id, str(e))
            logger.error(f"Background job crashed: {e}")


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("/enrich", response_model=JobStatus, status_code=202)
async def enrich_companies(
    request: EnrichRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    logger.info(f"Enriching companies: {request.companies}")
    service = JobService(db)
    logger.info(f"Creating job: {request.companies}")
    job = await service.create_job(request.companies)
    logger.info(f"Adding background task: {request.companies}")
    background_tasks.add_task(
        run_enrichment_job,
        job.job_id,
        request.companies
    )
    logger.info(f"Returning job: {request.companies}")
    return JobStatus.model_validate(job)


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(
    job_id: str,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    service = JobService(db)
    job = await service.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found"
        )
    return JobStatus.model_validate(job)


@router.get("/jobs", response_model=list[JobStatus])
async def list_jobs(db: Annotated[AsyncSession, Depends(get_db)]):
    service = JobService(db)
    jobs = await service.get_all_jobs()
    return [JobStatus.model_validate(j) for j in jobs]


@router.get("/companies", response_model=list[dict])
async def list_companies(db: Annotated[AsyncSession, Depends(get_db)]):
    """
    Returns all companies stored in long-term memory.
    This persists across server restarts — unlike the old dict.
    """
    result = await db.execute(
        select(CompanyMemory).order_by(CompanyMemory.enriched_at.desc())
    )
    companies = result.scalars().all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "domain": c.domain,
            "employee_count": c.employee_count,
            "industry": c.industry,
            "funding_stage": c.funding_stage,
            "enriched_at": c.enriched_at.isoformat()
        }
        for c in companies
    ]