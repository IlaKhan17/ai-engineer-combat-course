import asyncio
from src.ai_agent.services.enricher import CompanyEnricher


async def main():
    enricher = CompanyEnricher(max_retries=3)

    profiles, failures = await enricher.enrich_companies([
        "Atlan",
        "OpenAI", 
        "Anthropic",
        "Cohere",
        "INVALID_COMPANY"   # This one should fail gracefully
    ])

    print("\n" + "="*50)
    print(f"📊 RESULTS")
    print("="*50)

    print(f"\n✅ Successfully enriched ({len(profiles)}):")
    for p in profiles:
        print(f"   • {p.name} | {p.domain} | {p.employee_count} employees | {p.funding_stage}")

    print(f"\n❌ Failed ({len(failures)}):")
    for f in failures:
        print(f"   • {f}")


if __name__ == "__main__":
    asyncio.run(main())