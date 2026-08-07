import logging
from datetime import datetime, timezone
from typing import List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from shared.auth.dependencies import get_current_user, require_role
from shared.auth.rbac import UserRole
from shared.database.mongo import get_mongo_db
from shared.models.user import AppUser
from shared.utils.serialization import APIResponse

from ..schemas.resume import (
    GenerateLatexRequest,
    GenerateLatexResponse,
    ResumeTemplateResponse,
    SaveResumeRequest,
    SavedResumeResponse,
)
from ..services.latex_service import LatexService
from ..services.profile_service import ProfileService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resume", tags=["Resume"])


@router.get("/templates", response_model=APIResponse)
async def list_resume_templates():
    """Lists available LaTeX CV templates with metadata."""
    templates = LatexService.get_templates()
    return APIResponse(data=templates)


@router.post("/latex/generate", response_model=APIResponse)
async def generate_latex_resume(
    req: GenerateLatexRequest,
    user: AppUser = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """Generates compilable LaTeX code for candidate's profile."""
    profile_data = req.custom_profile
    if not profile_data:
        profile = await ProfileService.get_profile(db=db, user=user)
        profile_data = profile.model_dump()

    template = LatexService.get_template(req.template_id)
    latex_code = LatexService.generate_latex(req.template_id, profile_data)
    
    filename = f"{user.display_name.lower().replace(' ', '_') if user.display_name else 'candidate'}_resume.tex"

    resp = GenerateLatexResponse(
        template_id=template["id"],
        template_name=template["name"],
        latex_code=latex_code,
        suggested_filename=filename,
    )
    return APIResponse(data=resp)


@router.post("/save", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def save_custom_resume(
    req: SaveResumeRequest,
    user: AppUser = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """Saves a customized LaTeX resume version to candidate's storage."""
    coll = db["candidate_resumes"]
    now = datetime.now(timezone.utc).isoformat()
    doc_id = str(uuid4())

    doc = {
        "_id": doc_id,
        "id": doc_id,
        "user_id": user.id,
        "title": req.title,
        "template_id": req.template_id,
        "latex_code": req.latex_code,
        "created_at": now,
        "updated_at": now,
    }
    await coll.insert_one(doc)
    doc["id"] = str(doc.get("_id"))
    return APIResponse(message="Resume saved successfully", data=SavedResumeResponse.model_validate(doc))


@router.get("/my-resumes", response_model=APIResponse)
async def get_my_saved_resumes(
    user: AppUser = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """Fetches all saved LaTeX resumes for the current candidate."""
    coll = db["candidate_resumes"]
    cursor = coll.find({"user_id": user.id}).sort("updated_at", -1)
    docs = []
    async for d in cursor:
        d["id"] = str(d.get("_id"))
        docs.append(SavedResumeResponse.model_validate(d))
    return APIResponse(data=docs)


@router.delete("/{resume_id}", response_model=APIResponse)
async def delete_saved_resume(
    resume_id: str,
    user: AppUser = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """Deletes a saved custom resume."""
    coll = db["candidate_resumes"]
    res = await coll.delete_one({"_id": resume_id, "user_id": user.id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved resume not found")
    return APIResponse(message="Resume deleted successfully")
