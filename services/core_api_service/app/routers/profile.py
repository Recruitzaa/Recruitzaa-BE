import logging
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from shared.auth.dependencies import get_current_user, require_role
from shared.auth.rbac import UserRole
from shared.database.mongo import get_mongo_db
from shared.models.user import AppUser
from shared.utils.serialization import APIResponse
from ..models.candidate_profile import CandidateProfile, ResumeVersion
from ..schemas.profile import UpdateProfileRequest
from ..services.profile_service import ProfileService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("", response_model=APIResponse)
async def get_candidate_profile(
    user: AppUser = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    profile = await ProfileService.get_profile(db=db, user=user)
    return APIResponse(data=profile)


@router.put("", response_model=APIResponse)
async def update_candidate_profile(
    data: UpdateProfileRequest,
    user: AppUser = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    updated = await ProfileService.update_profile(db=db, user=user, data=data)
    return APIResponse(message="Profile updated successfully", data=updated)


@router.post("/resume", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume_file(
    file: UploadFile = File(...),
    user: AppUser = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File exceeds 10MB limit")

    content_type = file.content_type or "application/pdf"
    filename = file.filename or "resume.pdf"

    resume_ver = await ProfileService.upload_resume(
        db=db,
        user=user,
        filename=filename,
        file_bytes=file_bytes,
        content_type=content_type,
    )
    return APIResponse(message="Resume uploaded successfully", data=resume_ver)


@router.delete("/resume/{version_id}", response_model=APIResponse)
async def delete_resume_file(
    version_id: str,
    user: AppUser = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    deleted = await ProfileService.delete_resume(db=db, user=user, version_id=version_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume version not found")
    return APIResponse(message="Resume deleted successfully")
