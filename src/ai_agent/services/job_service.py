import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from src.ai_agent.models.database import CompanyJob, CompanyMemory
from src.ai_agent.models.company import CompanyProfile
import logging

logger = logging.getLogger(__name__)

def utc_now() -> datetime:
    # Avoid datetime.utcnow() to satisfy linter rules; keep naive UTC for DB columns.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class JobService:
    """
    Handles all database operations for enrichment jobs.
    This is the ONLY place that touches the DB — never write
    DB queries directly in your routes.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Create ────────────────────────────────────────────────────────────────
    async def create_job(self, company_names: list[str]) -> CompanyJob:
        """Creates a new pending job in the database."""
        job = CompanyJob(
            job_id=str(uuid.uuid4())[:8],
            status="pending",
            created_at=utc_now(),
            total=len(company_names),
            results=[],
            failures=[]
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)   # reload from DB to get all defaults
        logger.info(f"Created job {job.job_id}")
        return job

    # ── Read ──────────────────────────────────────────────────────────────────
    async def get_job(self, job_id: str) -> CompanyJob | None:
        """Fetch a single job by ID."""
        result = await self.db.execute(
            select(CompanyJob).where(CompanyJob.job_id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_all_jobs(self) -> list[CompanyJob]:
        """Fetch all jobs ordered by newest first."""
        result = await self.db.execute(
            select(CompanyJob).order_by(CompanyJob.created_at.desc())
        )
        return result.scalars().all()

    # ── Update ────────────────────────────────────────────────────────────────
    async def mark_running(self, job_id: str) -> None:
        """Mark job as running when background task starts."""
        await self.db.execute(
            update(CompanyJob)
            .where(CompanyJob.job_id == job_id)
            .values(status="running")
        )
        await self.db.commit()

    async def complete_job(
        self,
        job_id: str,
        profiles: list[CompanyProfile],
        failures: list[str]
    ) -> None:
        """Save final results when enrichment finishes."""
        await self.db.execute(
            update(CompanyJob)
            .where(CompanyJob.job_id == job_id)
            .values(
                status="completed",
                completed_at=utc_now(),
                successful=len(profiles),
                failed=len(failures),
                results=[p.model_dump(mode="json") for p in profiles],
                failures=failures
            )
        )
        await self.db.commit()
        logger.info(f"Job {job_id} completed — {len(profiles)} succeeded, {len(failures)} failed")

    async def fail_job(self, job_id: str, error: str) -> None:
        """Mark job as failed if something unexpected crashes."""
        await self.db.execute(
            update(CompanyJob)
            .where(CompanyJob.job_id == job_id)
            .values(status="failed")
        )
        await self.db.commit()
        logger.error(f"Job {job_id} failed: {error}")

    # ── Company Memory ────────────────────────────────────────────────────────
    async def save_companies(self, profiles: list[CompanyProfile]) -> None:
        """
        Save enriched companies to long-term memory.
        Uses INSERT ... ON CONFLICT DO UPDATE (upsert)
        so running the same company twice updates instead of errors.
        """
        for profile in profiles:
            # Check if company already exists
            result = await self.db.execute(
                select(CompanyMemory).where(
                    CompanyMemory.name == profile.name
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing record
                existing.domain = profile.domain
                existing.employee_count = profile.employee_count
                existing.industry = profile.industry
                existing.funding_stage = profile.funding_stage
                existing.enriched_at = utc_now()
                logger.info(f"Updated company: {profile.name}")
            else:
                # Insert new record
                company = CompanyMemory(
                    name=profile.name,
                    domain=profile.domain,
                    employee_count=profile.employee_count,
                    industry=profile.industry,
                    funding_stage=profile.funding_stage,
                    enriched_at=utc_now()
                )
                self.db.add(company)
                logger.info(f"Saved new company: {profile.name}")

        await self.db.commit()