from typing import Optional
from shared.utils.serialization import CamelModel
from ..models.candidate_profile import Skill, EmploymentStatus, SalaryExpectation

class UpdateProfileRequest(CamelModel):
    headline: Optional[str] = None
    bio: Optional[str] = None
    summary: Optional[str] = None
    personal_info: Optional[dict] = None
    skills: Optional[list[Skill]] = None
    skills_flat: Optional[list[str]] = None
    experience: Optional[list[dict]] = None
    education: Optional[list[dict]] = None
    projects: Optional[list[dict]] = None
    it_skills: Optional[list[dict]] = None
    certifications: Optional[list[dict]] = None
    career_profile: Optional[dict] = None
    extended_personal: Optional[dict] = None
    accomplishments: Optional[dict] = None
    preferred_job_types: Optional[list[str]] = None
    preferred_locations: Optional[list[str]] = None
    salary_expectation: Optional[SalaryExpectation] = None
    employment_status: Optional[EmploymentStatus] = None
    availability: Optional[str] = None
    languages: Optional[list[str]] = None
