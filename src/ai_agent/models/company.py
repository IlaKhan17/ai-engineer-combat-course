from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class CompanyProfile(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    domain: str = Field(..., description="Company website domain")
    employee_count: Optional[int] = Field(default=None, ge=1)
    industry: str = Field(default="Unknown")
    funding_stage: Optional[str] = Field(default=None)
    headquarters: Optional[str] = Field(default=None)   # ← new
    founded_year: Optional[int] = Field(default=None)   # ← new
    description: Optional[str] = Field(default=None)    # ← new
    enriched_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("domain")
    @classmethod
    def clean_domain(cls, v: str) -> str:
        return v.replace("https://", "").replace("http://", "").strip("/")

    @field_validator("funding_stage")
    @classmethod
    def validate_funding(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        valid = {"Seed", "Series A", "Series B", "Series C", "Public", "Bootstrapped"}
        if v not in valid:
            return None    # don't crash, just nullify invalid values
        return v