from datetime import datetime
from typing import Optional
from pydantic import Field, BaseModel

from shared.utils.serialization import CamelModel

class Skill(CamelModel):
    name: str
    level: Optional[str] = None
    years: Optional[int] = None

class ResumeVersion(CamelModel):
    url: str
    filename: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    is_primary: bool = False
    file_size_display: Optional[str] = None

class EmploymentStatus(CamelModel):
    is_employed: bool = False
    current_company: Optional[str] = None
    current_role: Optional[str] = None
    current_salary: Optional[str] = None
    notice_period: Optional[str] = None

class SalaryExpectation(CamelModel):
    min: Optional[int] = None
    max: Optional[int] = None
    currency: str = "INR"

class CandidateProfile(CamelModel):
    id: str = Field(alias="_id")
    user_id: str
    
    headline: Optional[str] = None
    bio: Optional[str] = None
    summary: Optional[str] = None
    
    personal_info: Optional[dict] = None
    skills: list[Skill] = Field(default_factory=list)
    skills_flat: list[str] = Field(default_factory=list)
    
    experience: list[dict] = Field(default_factory=list)
    education: list[dict] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    it_skills: list[dict] = Field(default_factory=list)
    certifications: list[dict] = Field(default_factory=list)
    
    career_profile: Optional[dict] = None
    extended_personal: Optional[dict] = None
    accomplishments: Optional[dict] = None
    
    resume_versions: list[ResumeVersion] = Field(default_factory=list)
    
    preferred_job_types: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    
    salary_expectation: Optional[SalaryExpectation] = None
    employment_status: Optional[EmploymentStatus] = None
    
    profile_completion_pct: int = 0
    availability: Optional[str] = None
    languages: list[str] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
