import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from shared.auth.dependencies import get_current_user, get_optional_current_user, require_role
from shared.auth.rbac import UserRole
from shared.database.mongo import get_mongo_db
from shared.models.user import AppUser
from shared.utils.serialization import APIResponse
from ..models.job import Job
from ..schemas.jobs import CreateJobRequest, UpdateJobRequest, JobFilterParams
from ..services.job_service import JobService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("", response_model=APIResponse)
async def search_jobs(
    keyword: Optional[str] = Query(None, description="Search across title, description, company, skills"),
    location: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    work_mode: Optional[str] = Query(None),
    min_salary: Optional[int] = Query(None),
    max_salary: Optional[int] = Query(None),
    posted_within: Optional[int] = Query(None, description="Filter jobs posted within N days"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: Optional[AppUser] = Depends(get_optional_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    params = JobFilterParams(
        keyword=keyword,
        location=location,
        job_type=job_type,
        work_mode=work_mode,
        min_salary=min_salary,
        max_salary=max_salary,
        posted_within=posted_within,
        page=page,
        page_size=page_size,
    )
    user_id = user.id if user else None
    result = await JobService.search_jobs(db, params, user_id=user_id)
    return APIResponse(data=result)


@router.get("/{job_id}", response_model=APIResponse)
async def get_job_detail(
    job_id: str,
    user: Optional[AppUser] = Depends(get_optional_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    user_id = user.id if user else None
    job = await JobService.get_job_by_id(db, job_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return APIResponse(data=job)


@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    data: CreateJobRequest,
    user: AppUser = Depends(require_role(UserRole.EMPLOYER, UserRole.SUPER_ADMIN)),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    company_name = data.company or (user.current_company or user.display_name or "Company")
    data.company = company_name
    job = await JobService.create_job(db, employer_id=user.id, data=data)
    return APIResponse(message="Job created successfully", data=job)


@router.put("/{job_id}", response_model=APIResponse)
async def update_job(
    job_id: str,
    data: UpdateJobRequest,
    user: AppUser = Depends(require_role(UserRole.EMPLOYER, UserRole.SUPER_ADMIN)),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    job = await JobService.update_job(db, job_id=job_id, employer_id=user.id, data=data)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found or permission denied")
    return APIResponse(message="Job updated successfully", data=job)


@router.delete("/{job_id}", response_model=APIResponse)
async def delete_job(
    job_id: str,
    user: AppUser = Depends(require_role(UserRole.EMPLOYER, UserRole.SUPER_ADMIN)),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    success = await JobService.delete_job(db, job_id=job_id, employer_id=user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found or permission denied")
    return APIResponse(message="Job closed successfully")
