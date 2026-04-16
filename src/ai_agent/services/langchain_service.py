import logging
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from pydantic import BaseModel, Field
from typing import Optional
from src.ai_agent.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Output Schema ─────────────────────────────────────────────────────────────
class CompanyResearchOutput(BaseModel):
    """
    This tells LangChain exactly what JSON structure to expect.
    It generates format instructions automatically from this class.
    """
    name: str = Field(description="Official company name")
    domain: str = Field(description="Company domain without https://")
    employee_count: Optional[int] = Field(description="Number of employees or null")
    industry: str = Field(description="Primary industry")
    funding_stage: Optional[str] = Field(description="Seed/Series A/B/C/Public/Bootstrapped or null")
    headquarters: Optional[str] = Field(description="City, Country")
    founded_year: Optional[int] = Field(description="Year founded or null")
    description: str = Field(description="One sentence description")


class LangChainService:
    """
    Production LangChain service.
    Replaces our manual LLMService with proper chains.
    """

    def __init__(self):
        # ── LLM ───────────────────────────────────────────────────────────────
        self.llm = ChatOpenAI(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            temperature=0.1
        )

        # ── Parser ────────────────────────────────────────────────────────────
        self.json_parser = JsonOutputParser(
            pydantic_object=CompanyResearchOutput
        )
        self.str_parser = StrOutputParser()

        # ── Chains ────────────────────────────────────────────────────────────
        self._build_chains()

    def _build_chains(self):
        """
        Build all chains once at startup.
        Chains are reusable — build once, invoke many times.
        """

        # Chain 1: Company Research Chain
        research_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                """You are a professional business intelligence analyst.
                Return accurate, structured data about companies.
                {format_instructions}"""
            ),
            (
                "human",
                "Research this company and return structured data: {company_name}"
            )
        ])

        self.research_chain = (
            research_prompt
            | self.llm
            | self.json_parser
        )

        # Chain 2: Company Summary Chain (plain text output)
        summary_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are a business analyst. Write clear, concise company summaries."
            ),
            (
                "human",
                """Write a 3 sentence investor summary for {company_name}.
                Known facts: {company_facts}
                Focus on: what they do, market opportunity, why they matter."""
            )
        ])

        self.summary_chain = (
            summary_prompt
            | self.llm
            | self.str_parser
        )

        # Chain 3: Combined Chain (research + summary in sequence)
        # This is a SEQUENTIAL chain — output of research feeds into summary
        self.full_chain = (
            RunnablePassthrough.assign(
                research=self.research_chain
            )
        )

    async def research_company(self, company_name: str) -> dict:
        """Research a company and return structured data."""
        logger.info(f"🔍 Researching: {company_name}")

        result = await self.research_chain.ainvoke({
            "company_name": company_name,
            "format_instructions": self.json_parser.get_format_instructions()
        })

        logger.info(f"✅ Research complete: {company_name}")
        return result

    async def summarize_company(
        self,
        company_name: str,
        company_facts: str
    ) -> str:
        """Generate an investor summary for a company."""
        logger.info(f"📝 Summarizing: {company_name}")

        result = await self.summary_chain.ainvoke({
            "company_name": company_name,
            "company_facts": company_facts
        })

        return result

    async def research_and_summarize(self, company_name: str) -> dict:
        """
        Full pipeline:
        1. Research company → structured data
        2. Generate investor summary from that data
        Returns both research + summary
        """
        # Step 1: Research
        research = await self.research_company(company_name)

        # Step 2: Summarize using research as context
        facts = f"""
        Industry: {research.get('industry')}
        Founded: {research.get('founded_year')}
        Employees: {research.get('employee_count')}
        Funding: {research.get('funding_stage')}
        HQ: {research.get('headquarters')}
        """

        summary = await self.summarize_company(company_name, facts)

        # Combine both
        return {
            **research,
            "investor_summary": summary
        }