from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4
from pydantic import Field

from shared.utils.serialization import CamelModel

class JobStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CLOSED = "CLOSED"

class JobType(str, Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"
    INTERNSHIP = "INTERNSHIP"

class WorkMode(str, Enum):
    REMOTE = "REMOTE"
    HYBRID = "HYBRID"
    ONSITE = "ONSITE"

class Job(CamelModel):
    id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    employer_id: str
    company_id: Optional[str] = None
    company: str
    title: str
    description: str
    location: str
    job_type: str = JobType.FULL_TIME.value
    work_mode: str = WorkMode.ONSITE.value
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "INR"
    status: JobStatus = JobStatus.APPROVED  # default approved for dev/direct posting, or PENDING if approval needed
    tags: list[str] = Field(default_factory=list)
    skills_required: list[str] = Field(default_factory=list)
    applicants_count: int = 0
    posted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Enrichment fields when queried by authenticated candidate
    ai_match_score: Optional[int] = None
    is_saved: Optional[bool] = None
    application_status: Optional[str] = None
