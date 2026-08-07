import logging
from datetime import datetime, timezone
from typing import Optional, Any
from uuid import uuid4

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from shared.messaging.kafka_producer import get_producer
from shared.messaging.topics import APPLICATION_CREATED, APPLICATION_STAGE_MOVED
from ..models.application import Application, ApplicationStage
from ..schemas.applications import ApplyJobRequest

logger = logging.getLogger(__name__)


class ApplicationService:
    @staticmethod
    async def get_applications_coll(db: AsyncIOMotorDatabase):
        return db["applications"]

    @staticmethod
    async def get_jobs_coll(db: AsyncIOMotorDatabase):
        return db["jobs"]

    @classmethod
    async def apply_job(
        cls,
        db: AsyncIOMotorDatabase,
        candidate_id: str,
        job_id: str,
        data: ApplyJobRequest,
    ) -> Application:
        jobs_coll = await cls.get_jobs_coll(db)
        job = await jobs_coll.find_one({"_id": job_id})
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

        apps_coll = await cls.get_applications_coll(db)
        existing = await apps_coll.find_one({"job_id": job_id, "candidate_id": candidate_id})
        
        now = datetime.now(timezone.utc)
        if existing:
            if existing.get("stage") != ApplicationStage.SAVED.value and existing.get("stage") != "SAVED":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"You have already applied for this job (current stage: {existing.get('stage')})"
                )
            
            # Upgrade SAVED card to APPLIED
            app_id = str(existing.get("_id"))
            update_data = {
                "stage": ApplicationStage.APPLIED.value,
                "resume_url": data.resume_url or existing.get("resume_url"),
                "cover_letter": data.cover_letter or existing.get("cover_letter"),
                "applied_at": now,
                "updated_at": now,
            }
            updated = await apps_coll.find_one_and_update(
                {"_id": app_id},
                {"$set": update_data},
                return_document=True,
            )
            await jobs_coll.update_one({"_id": job_id}, {"$inc": {"applicants_count": 1}})
            app_doc = updated
        else:
            app_id = str(uuid4())
            app_dict = {
                "_id": app_id,
                "id": app_id,
                "job_id": job_id,
                "job_title": job.get("title", ""),
                "company": job.get("company", ""),
                "candidate_id": candidate_id,
                "employer_id": job.get("employer_id", ""),
                "stage": ApplicationStage.APPLIED.value,
                "resume_url": data.resume_url,
                "cover_letter": data.cover_letter,
                "applied_at": now,
                "created_at": now,
                "updated_at": now,
            }
            await apps_coll.insert_one(app_dict)
            await jobs_coll.update_one({"_id": job_id}, {"$inc": {"applicants_count": 1}})
            app_doc = app_dict

        # Emit Kafka event
        try:
            producer = await get_producer()
            await producer.send_event(
                APPLICATION_CREATED,
                {
                    "application_id": app_id,
                    "job_id": job_id,
                    "candidate_id": candidate_id,
                    "employer_id": job.get("employer_id", ""),
                },
                key=app_id,
            )
        except Exception as exc:
            logger.warning("Kafka application.created event failed: %s", exc)

        app_doc["id"] = str(app_doc.get("_id"))
        return Application.model_validate(app_doc)

    @classmethod
    async def get_candidate_applications(
        cls,
        db: AsyncIOMotorDatabase,
        candidate_id: str,
        stage: Optional[ApplicationStage] = None,
    ) -> list[Application]:
        apps_coll = await cls.get_applications_coll(db)
        query: dict[str, Any] = {"candidate_id": candidate_id}
        if stage:
            query["stage"] = stage.value if hasattr(stage, "value") else stage

        cursor = apps_coll.find(query).sort("applied_at", -1)
        docs = await cursor.to_list(length=200)
        results = []
        for doc in docs:
            doc["id"] = str(doc.get("_id"))
            results.append(Application.model_validate(doc))
        return results

    @classmethod
    async def update_stage(
        cls,
        db: AsyncIOMotorDatabase,
        application_id: str,
        user_id: str,
        new_stage: ApplicationStage,
    ) -> Application:
        apps_coll = await cls.get_applications_coll(db)
        app = await apps_coll.find_one({"_id": application_id})
        if not app:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

        stage_val = new_stage.value if hasattr(new_stage, "value") else new_stage
        now = datetime.now(timezone.utc)
        updated = await apps_coll.find_one_and_update(
            {"_id": application_id},
            {"$set": {"stage": stage_val, "updated_at": now}},
            return_document=True,
        )

        try:
            producer = await get_producer()
            await producer.send_event(
                APPLICATION_STAGE_MOVED,
                {
                    "application_id": application_id,
                    "candidate_id": app.get("candidate_id"),
                    "job_id": app.get("job_id"),
                    "old_stage": app.get("stage"),
                    "new_stage": stage_val,
                },
                key=application_id,
            )
        except Exception as exc:
            logger.warning("Kafka application.stage.moved event failed: %s", exc)

        updated["id"] = str(updated.get("_id"))
        return Application.model_validate(updated)

    @classmethod
    async def withdraw_application(
        cls,
        db: AsyncIOMotorDatabase,
        application_id: str,
        candidate_id: str,
    ) -> bool:
        apps_coll = await cls.get_applications_coll(db)
        res = await apps_coll.delete_one({"_id": application_id, "candidate_id": candidate_id})
        return res.deleted_count > 0

    @classmethod
    async def get_employer_applications(
        cls,
        db: AsyncIOMotorDatabase,
        employer_id: str,
        job_id: Optional[str] = None,
    ) -> list[Application]:
        apps_coll = await cls.get_applications_coll(db)
        query: dict[str, Any] = {"employer_id": employer_id}
        if job_id:
            query["job_id"] = job_id
        cursor = apps_coll.find(query).sort("applied_at", -1)
        docs = await cursor.to_list(length=500)
        results = []
        for doc in docs:
            doc["id"] = str(doc.get("_id"))
            results.append(Application.model_validate(doc))
        return results
