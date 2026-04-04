import asyncio
import logging
from typing import Optional
from pydantic import ValidationError

from src.ai_agent.models.company import CompanyProfile
from src.ai_agent.services.llm_service import LLMService
from src.ai_agent.utils.prompts import (
    COMPANY_RESEARCH_SYSTEM,
    COMPANY_RESEARCH_USER
)

logger = logging.getLogger(__name__)


class CompanyEnricher:
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.llm = LLMService()

    async def _research_company(self, name: str) -> Optional[dict]:
        """
        Uses GPT-4 to research a company and return structured data.
        This replaces our fake MOCK_COMPANY_DATA dict.
        """
        prompt = COMPANY_RESEARCH_USER.format(company_name=name)

        for attempt in range(1, self.max_retries + 1):
            try:
                # Ask LLM to return structured JSON
                data = await self.llm.complete_json(
                    system_prompt=COMPANY_RESEARCH_SYSTEM,
                    user_message=prompt
                )
                logger.info(f"✅ Researched: {name} (attempt {attempt})")
                return data

            except Exception as e:
                wait_time = 2 ** (attempt - 1)
                logger.warning(f"⚠️ Failed researching {name}: {e} — retrying in {wait_time}s")
                await asyncio.sleep(wait_time)

        logger.error(f"All attempts failed for: {name}")
        return None

    async def enrich_companies(
        self,
        company_names: list[str]
    ) -> tuple[list[CompanyProfile], list[str]]:
        """
        Researches all companies concurrently using real AI.
        """
        logger.info(f"AI researching {len(company_names)} companies...")

        # All LLM calls run simultaneously
        tasks = [self._research_company(name) for name in company_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful: list[CompanyProfile] = []
        failed: list[str] = []

        for name, result in zip(company_names, results):
            if isinstance(result, Exception):
                logger.error(f"Unexpected error for {name}: {result}")
                failed.append(name)
                continue

            if result is None:
                failed.append(name)
                continue

            try:
                # Validate LLM output against our Pydantic model
                profile = CompanyProfile(**result)
                successful.append(profile)
                logger.info(f"Validated: {profile.name} | {profile.industry}")
            except ValidationError as e:
                logger.error(f"Validation failed for {name}: {e}")
                failed.append(name)

        logger.info(f"✅ Done — {len(successful)} succeeded, {len(failed)} failed")
        return successful, failed