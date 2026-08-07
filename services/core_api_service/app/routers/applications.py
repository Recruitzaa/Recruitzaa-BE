import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from shared.auth.dependencies import get_current_user, require_role
from shared.auth.rbac import UserRole
from shared.database.mongo import get_mongo_db
from shared.models.user import AppUser
from shared.utils.serialization import APIResponse
from ..models.application import Application, ApplicationStage
from ..schemas.applications import ApplyJobRequest, UpdateApplicationStageRequest
from ..services.application_service import ApplicationService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Applications"])


@router.post("/jobs/{job_id}/apply", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def apply_to_job(
    job_id: str,
    data: ApplyJobRequest,
    user: AppUser = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    app_doc = await ApplicationService.apply_job(
        db=db,
        candidate_id=user.id,
        job_id=job_id,
        data=data,
    )
    return APIResponse(message="Application submitted successfully", data=app_doc)


@router.get("/applications", response_model=APIResponse)
async def get_my_applications(
    stage: Optional[ApplicationStage] = Query(None),
    user: AppUser = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    apps = await ApplicationService.get_candidate_applications(
        db=db,
        candidate_id=user.id,
        stage=stage,
    )
    return APIResponse(data=apps)


@router.patch("/applications/{application_id}/stage", response_model=APIResponse)
async def update_application_stage(
    application_id: str,
    data: UpdateApplicationStageRequest,
    user: AppUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    updated = await ApplicationService.update_stage(
        db=db,
        application_id=application_id,
        user_id=user.id,
        new_stage=data.stage,
    )
    return APIResponse(message="Stage updated successfully", data=updated)


@router.post("/applications/{application_id}/withdraw", response_model=APIResponse)
async def withdraw_application(
    application_id: str,
    user: AppUser = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    success = await ApplicationService.withdraw_application(
        db=db,
        application_id=application_id,
        candidate_id=user.id,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return APIResponse(message="Application withdrawn successfully")
