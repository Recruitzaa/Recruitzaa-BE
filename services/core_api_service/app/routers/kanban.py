import logging
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from shared.auth.dependencies import require_role
from shared.auth.rbac import UserRole
from shared.database.mongo import get_mongo_db
from shared.models.user import AppUser
from shared.utils.serialization import APIResponse
from ..schemas.applications import SaveJobRequest
from ..schemas.kanban import MoveKanbanCardRequest
from ..services.kanban_service import KanbanService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kanban", tags=["Kanban"])


@router.get("", response_model=APIResponse)
async def get_kanban_board(
    user: AppUser = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    board = await KanbanService.get_board(db=db, candidate_id=user.id)
    return APIResponse(data=board)


@router.put("/move", response_model=APIResponse)
async def move_kanban_card(
    data: MoveKanbanCardRequest,
    user: AppUser = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    updated = await KanbanService.move_card(
        db=db,
        candidate_id=user.id,
        application_id=data.application_id,
        to_stage=data.to_stage,
        position=data.position,
    )
    return APIResponse(message="Card moved successfully", data=updated)


@router.post("/save", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def save_job_to_kanban(
    data: SaveJobRequest,
    user: AppUser = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    card = await KanbanService.save_job(
        db=db,
        candidate_id=user.id,
        job_id=data.job_id,
    )
    return APIResponse(message="Job saved to Kanban", data=card)


@router.delete("/save/{job_id}", response_model=APIResponse)
async def remove_saved_job_from_kanban(
    job_id: str,
    user: AppUser = Depends(require_role(UserRole.CANDIDATE)),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    removed = await KanbanService.remove_saved_job(
        db=db,
        candidate_id=user.id,
        job_id=job_id,
    )
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved job not found")
    return APIResponse(message="Job removed from saved")
