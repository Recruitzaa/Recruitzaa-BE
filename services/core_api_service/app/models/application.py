from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4
from pydantic import Field

from shared.utils.serialization import CamelModel

class ApplicationStage(str, Enum):
    SAVED = "SAVED"
    APPLIED = "APPLIED"
    SCREENING = "SCREENING"
    INTERVIEW = "INTERVIEW"
    OFFER = "OFFER"
    REJECTED = "REJECTED"

class Application(CamelModel):
    id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    job_id: str
    job_title: str
    company: str
    candidate_id: str
    employer_id: str
    
    stage: ApplicationStage = ApplicationStage.APPLIED
    resume_url: Optional[str] = None
    cover_letter: Optional[str] = None
    
    ai_match_score: Optional[int] = None
    
    applied_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
