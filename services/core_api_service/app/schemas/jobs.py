from datetime import datetime
from typing import Optional
from pydantic import Field
from shared.utils.serialization import CamelModel
from ..models.job import Job, JobStatus, JobType, WorkMode

class CreateJobRequest(CamelModel):
    title: str
    company: str
    company_id: Optional[str] = None
    description: str
    location: str
    job_type: JobType = JobType.FULL_TIME
    work_mode: WorkMode = WorkMode.ONSITE
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "INR"
    tags: list[str] = Field(default_factory=list)
    skills_required: list[str] = Field(default_factory=list)

class UpdateJobRequest(CamelModel):
    title: Optional[str] = None
    company: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[JobType] = None
    work_mode: Optional[WorkMode] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    status: Optional[JobStatus] = None
    tags: Optional[list[str]] = None
    skills_required: Optional[list[str]] = None

class JobFilterParams(CamelModel):
    keyword: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = None
    work_mode: Optional[str] = None
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    posted_within: Optional[int] = None  # in days
    page: int = 1
    page_size: int = 20
