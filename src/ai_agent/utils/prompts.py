# This is where ALL your prompts live
# Never hardcode prompts inside service files
# Prompts are like configuration — they change often

COMPANY_RESEARCH_SYSTEM = """
You are a professional business intelligence analyst.
Your job is to return accurate, structured data about companies.

CRITICAL RULES:
- Always respond with valid JSON only
- If you don't know a value, use null (never guess)
- employee_count must be an integer or null
- funding_stage must be one of: Seed, Series A, Series B, Series C, Public, Bootstrapped, or null
- domain must be just the domain (e.g. "atlan.com" not "https://atlan.com")
- Be concise and factual, no explanations
"""

COMPANY_RESEARCH_USER = """
Research this company and return a JSON object with exactly these fields:

Company: {company_name}

Return JSON with these exact keys:
{{
    "name": "official company name",
    "domain": "company domain without https://",
    "employee_count": integer or null,
    "industry": "primary industry",
    "funding_stage": "Seed/Series A/Series B/Series C/Public/Bootstrapped or null",
    "headquarters": "City, Country",
    "founded_year": integer or null,
    "description": "one sentence description"
}}
"""

# You'll add more prompts here as the course progresses
# Day 8: Agent system prompts
# Day 9: Multi-agent coordination prompts
# Day 12: Evaluation prompts