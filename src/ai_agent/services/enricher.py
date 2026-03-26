import asyncio
import logging
import random
from typing import Optional
from datetime import datetime

from src.ai_agent.models.company import CompanyProfile
from src.ai_agent.config import get_settings

# Professional logging setup — never use print() in services
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# ── Mock Database ─────────────────────────────────────────────────────────────
# This simulates an external API response (like Clearbit or Apollo.io)
MOCK_COMPANY_DATA: dict[str, dict] = {
    "atlan": {
        "name": "Atlan",
        "domain": "https://atlan.com",
        "employee_count": 200,
        "industry": "Data & AI",
        "funding_stage": "Series B"
    },
    "openai": {
        "name": "OpenAI",
        "domain": "https://openai.com",
        "employee_count": 900,
        "industry": "Artificial Intelligence",
        "funding_stage": "Series C"
    },
    "anthropic": {
        "name": "Anthropic",
        "domain": "https://anthropic.com",
        "employee_count": 400,
        "industry": "Artificial Intelligence",
        "funding_stage": "Series C"
    },
    "cohere": {
        "name": "Cohere",
        "domain": "https://cohere.com",
        "employee_count": 300,
        "industry": "Natural Language Processing",
        "funding_stage": "Series C"
    }
}


# ── Core Service ──────────────────────────────────────────────────────────────
class CompanyEnricher:
    def __init__(self, max_retries: int = 3):
        self.settings = get_settings()
        self.max_retries = max_retries

    async def _fetch_company_data(self, name: str) -> dict:
        """
        Simulates an async API call to an external data provider.
        In production this would be: await client.get(f"https://api.clearbit.com/v2/companies/{name}")
        """
        # Simulate network delay (0.5 to 1.5 seconds)
        await asyncio.sleep(random.uniform(0.5, 1.5))

        key = name.lower()

        # Simulate 20% random failure rate (real APIs fail too!)
        if random.random() < 0.2:
            raise ConnectionError(f"Network timeout fetching {name}")

        # Simulate unknown company
        if key not in MOCK_COMPANY_DATA:
            raise ValueError(f"Company '{name}' not found in database")

        return MOCK_COMPANY_DATA[key]

    async def _fetch_with_retry(self, name: str) -> Optional[dict]:
        """
        Retries a failed fetch with exponential backoff.
        
        Exponential backoff means:
        - Attempt 1 fails → wait 1 second
        - Attempt 2 fails → wait 2 seconds  
        - Attempt 3 fails → wait 4 seconds
        - Then give up
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                data = await self._fetch_company_data(name)
                logger.info(f"Fetched: {name} (attempt {attempt})")
                return data

            except ConnectionError as e:
                wait_time = 2 ** (attempt - 1)  # 1, 2, 4 seconds
                logger.warning(f"Warning: {e} — retrying in {wait_time}s (attempt {attempt}/{self.max_retries})")
                await asyncio.sleep(wait_time)

            except ValueError as e:
                # Don't retry if company simply doesn't exist
                logger.error(f"Error: {e}")
                return None

        logger.error(f"Error: All {self.max_retries} attempts failed for: {name}")
        return None

    async def enrich_companies(
        self,
        company_names: list[str]
    ) -> tuple[list[CompanyProfile], list[str]]:
        """
        Fetches all companies CONCURRENTLY using asyncio.gather().
        
        Without gather: 5 companies × 1.5s = 7.5 seconds total
        With gather:    all 5 run at same time = ~1.5 seconds total
        """
        logger.info(f"Starting enrichment for {len(company_names)} companies...")

        # Launch all fetches at the same time
        tasks = [self._fetch_with_retry(name) for name in company_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # ── Process Results ───────────────────────────────────────────────────
        successful: list[CompanyProfile] = []
        failed: list[str] = []

        for name, result in zip(company_names, results):
            # gather() with return_exceptions=True means exceptions
            # come back as values — we check for them manually
            if isinstance(result, Exception):
                logger.error(f"Unexpected error for {name}: {result}")
                failed.append(name)
                continue

            if result is None:
                failed.append(name)
                continue

            # Validate raw dict → CompanyProfile (Pydantic does the work)
            try:
                profile = CompanyProfile(**result)
                successful.append(profile)
            except Exception as e:
                logger.error(f"Validation failed for {name}: {e}")
                failed.append(name)

        logger.info(f"Done — {len(successful)} succeeded, {len(failed)} failed")
        return successful, failed