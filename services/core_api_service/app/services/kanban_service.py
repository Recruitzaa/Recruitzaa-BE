import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..models.application import Application, ApplicationStage
from ..models.kanban import KanbanCard, KanbanBoardResponse
from .application_service import ApplicationService

logger = logging.getLogger(__name__)


class KanbanService:
    @staticmethod
    async def get_applications_coll(db: AsyncIOMotorDatabase):
        return db["applications"]

    @staticmethod
    async def get_jobs_coll(db: AsyncIOMotorDatabase):
        return db["jobs"]

    @classmethod
    async def get_board(cls, db: AsyncIOMotorDatabase, candidate_id: str) -> KanbanBoardResponse:
        apps_coll = await cls.get_applications_coll(db)
        cursor = apps_coll.find({"candidate_id": candidate_id}).sort("applied_at", -1)
        docs = await cursor.to_list(length=500)

        board = KanbanBoardResponse()
        for idx, doc in enumerate(docs):
            doc_id = str(doc.get("_id"))
            card = KanbanCard(
                id=doc_id,
                job_id=doc.get("job_id", ""),
                job_title=doc.get("job_title", ""),
                company=doc.get("company", ""),
                stage=doc.get("stage", ApplicationStage.SAVED.value),
                applied_at=doc.get("applied_at"),
                ai_match_score=doc.get("ai_match_score"),
                position=idx,
            )
            stage_str = str(doc.get("stage", "")).upper()
            if stage_str == "SAVED":
                board.saved.append(card)
            elif stage_str == "APPLIED":
                board.applied.append(card)
            elif stage_str == "SCREENING":
                board.screening.append(card)
            elif stage_str == "INTERVIEW":
                board.interview.append(card)
            elif stage_str == "OFFER":
                board.offer.append(card)
            elif stage_str == "REJECTED":
                board.rejected.append(card)

        return board

    @classmethod
    async def save_job(cls, db: AsyncIOMotorDatabase, candidate_id: str, job_id: str) -> KanbanCard:
        jobs_coll = await cls.get_jobs_coll(db)
        job = await jobs_coll.find_one({"_id": job_id})
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

        apps_coll = await cls.get_applications_coll(db)
        existing = await apps_coll.find_one({"job_id": job_id, "candidate_id": candidate_id})
        now = datetime.now(timezone.utc)

        if existing:
            doc_id = str(existing.get("_id"))
            return KanbanCard(
                id=doc_id,
                job_id=job_id,
                job_title=job.get("title", ""),
                company=job.get("company", ""),
                stage=existing.get("stage", ApplicationStage.SAVED.value),
                applied_at=existing.get("applied_at"),
                ai_match_score=existing.get("ai_match_score"),
            )

        app_id = str(uuid4())
        app_dict = {
            "_id": app_id,
            "id": app_id,
            "job_id": job_id,
            "job_title": job.get("title", ""),
            "company": job.get("company", ""),
            "candidate_id": candidate_id,
            "employer_id": job.get("employer_id", ""),
            "stage": ApplicationStage.SAVED.value,
            "applied_at": now,
            "created_at": now,
            "updated_at": now,
        }
        await apps_coll.insert_one(app_dict)

        return KanbanCard(
            id=app_id,
            job_id=job_id,
            job_title=job.get("title", ""),
            company=job.get("company", ""),
            stage=ApplicationStage.SAVED,
            applied_at=now,
        )

    @classmethod
    async def remove_saved_job(cls, db: AsyncIOMotorDatabase, candidate_id: str, job_id: str) -> bool:
        apps_coll = await cls.get_applications_coll(db)
        res = await apps_coll.delete_one({
            "job_id": job_id,
            "candidate_id": candidate_id,
            "stage": {"$in": [ApplicationStage.SAVED.value, "SAVED"]},
        })
        return res.deleted_count > 0

    @classmethod
    async def move_card(
        cls,
        db: AsyncIOMotorDatabase,
        candidate_id: str,
        application_id: str,
        to_stage: ApplicationStage,
        position: int = 0,
    ) -> Application:
        return await ApplicationService.update_stage(
            db=db,
            application_id=application_id,
            user_id=candidate_id,
            new_stage=to_stage,
        )
