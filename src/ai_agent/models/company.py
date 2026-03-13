from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class CompanyProfile(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    domain: str = Field(..., description="Company website domain")
    employee_count: Optional[int] = Field(default=None, ge=1)
    industry: str = Field(default="Unknown")
    funding_stage: Optional[str] = Field(
        default=None,
        description="e.g. Seed, Series A, Series B, Public"
    )
    enriched_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("domain")
    @classmethod
    def clean_domain(cls, v: str) -> str:
        # Remove https:// or http:// if someone passes full URL
        return v.replace("https://", "").replace("http://", "").strip("/")

    @field_validator("funding_stage")
    @classmethod
    def validate_funding(cls, v: Optional[str]) -> Optional[str]:
        valid_stages = {"Seed", "Series A", "Series B", "Series C", "Public", "Bootstrapped"}
        if v and v not in valid_stages:
            raise ValueError(f"funding_stage must be one of {valid_stages}")
        return v