import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from shared.database.postgres import get_db_session
from shared.messaging.kafka_producer import get_producer
from shared.messaging.topics import AI_PARSE_REQUEST
from shared.models.user import AppUser
from shared.storage.minio_client import upload_file, delete_file
from ..models.candidate_profile import CandidateProfile, ResumeVersion, Skill, EmploymentStatus, SalaryExpectation
from ..schemas.profile import UpdateProfileRequest

logger = logging.getLogger(__name__)


class ProfileService:
    @staticmethod
    async def get_profiles_coll(db: AsyncIOMotorDatabase):
        return db["candidate_profiles"]

    @classmethod
    async def get_profile(cls, db: AsyncIOMotorDatabase, user: AppUser) -> CandidateProfile:
        coll = await cls.get_profiles_coll(db)
        doc = await coll.find_one({"user_id": user.id})
        
        if not doc:
            now = datetime.now(timezone.utc)
            doc = {
                "_id": str(uuid4()),
                "id": str(uuid4()),
                "user_id": user.id,
                "display_name": user.display_name,
                "headline": user.bio or "",
                "bio": user.bio or "",
                "summary": user.summary or "",
                "skills": [],
                "skills_flat": user.skills or [],
                "experience": [],
                "education": [],
                "certifications": [],
                "resume_versions": [],
                "preferred_job_types": [],
                "preferred_locations": [user.location] if user.location else [],
                "salary_expectation": None,
                "employment_status": {
                    "is_employed": user.is_currently_employed,
                    "current_company": user.current_company,
                    "current_role": user.current_role,
                    "current_salary": user.current_salary,
                    "notice_period": user.notice_period,
                },
                "profile_completion_pct": 20 if user.display_name else 10,
                "availability": "IMMEDIATE",
                "languages": [],
                "created_at": now,
                "updated_at": now,
            }
            await coll.insert_one(doc)

        doc["id"] = str(doc.get("_id"))
        return CandidateProfile.model_validate(doc)

    @classmethod
    async def update_profile(
        cls,
        db: AsyncIOMotorDatabase,
        user: AppUser,
        data: UpdateProfileRequest,
    ) -> CandidateProfile:
        coll = await cls.get_profiles_coll(db)
        now = datetime.now(timezone.utc)
        
        # Ensure profile exists
        existing = await coll.find_one({"user_id": user.id})
        if not existing:
            await cls.get_profile(db, user)

        update_fields = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
        update_fields["updated_at"] = now

        # Calculate completion percentage
        completion = 30
        if update_fields.get("headline") or (existing and existing.get("headline")):
            completion += 15
        if update_fields.get("skills") or (existing and existing.get("skills")):
            completion += 20
        if update_fields.get("experience") or (existing and existing.get("experience")):
            completion += 20
        if (existing and existing.get("resume_versions")):
            completion += 15
        update_fields["profile_completion_pct"] = min(100, completion)

        updated_doc = await coll.find_one_and_update(
            {"user_id": user.id},
            {"$set": update_fields},
            return_document=True,
        )

        # Sync profile to PostgreSQL user_profiles if relevant fields changed
        try:
            from services.auth_service.app.models.user import UserProfile
            async with get_db_session() as session:
                pg_updates = {}
                if data.bio is not None:
                    pg_updates["bio"] = data.bio
                if data.summary is not None:
                    pg_updates["summary"] = data.summary
                if data.employment_status is not None:
                    pg_updates["is_employed"] = data.employment_status.is_employed
                    pg_updates["current_company"] = data.employment_status.current_company
                    pg_updates["current_role"] = data.employment_status.current_role
                    pg_updates["current_salary"] = data.employment_status.current_salary
                    pg_updates["notice_period"] = data.employment_status.notice_period

                if pg_updates:
                    await session.execute(
                        update(UserProfile).where(UserProfile.user_id == user.id).values(**pg_updates)
                    )
        except Exception as exc:
            logger.warning("Failed to sync profile update to PostgreSQL: %s", exc)

        updated_doc["id"] = str(updated_doc.get("_id"))
        return CandidateProfile.model_validate(updated_doc)

    @classmethod
    async def upload_resume(
        cls,
        db: AsyncIOMotorDatabase,
        user: AppUser,
        filename: str,
        file_bytes: bytes,
        content_type: str,
    ) -> ResumeVersion:
        version_id = str(uuid4())
        ext = filename.split(".")[-1] if "." in filename else "pdf"
        object_name = f"{user.id}/{version_id}.{ext}"
        
        bucket = "resumes"
        url = upload_file(bucket=bucket, object_name=object_name, data=file_bytes, content_type=content_type)
        
        file_size_mb = f"{len(file_bytes) / (1024 * 1024):.1f} MB"
        resume_ver = ResumeVersion(
            url=url,
            filename=filename,
            uploaded_at=datetime.now(timezone.utc),
            is_primary=True,
            file_size_display=file_size_mb,
        )

        coll = await cls.get_profiles_coll(db)
        # Mark other resumes as non-primary, then add new resume
        await coll.update_one(
            {"user_id": user.id},
            {"$set": {"resume_versions.$[].is_primary": False}},
        )
        await coll.update_one(
            {"user_id": user.id},
            {"$push": {"resume_versions": resume_ver.model_dump()}},
            upsert=True,
        )

        # Trigger AI parse request event
        try:
            producer = await get_producer()
            await producer.send_event(
                AI_PARSE_REQUEST,
                {
                    "user_id": user.id,
                    "resume_url": url,
                    "filename": filename,
                    "version_id": version_id,
                },
                key=user.id,
            )
        except Exception as exc:
            logger.warning("Kafka ai.parse.request failed to send: %s", exc)

        return resume_ver

    @classmethod
    async def delete_resume(
        cls,
        db: AsyncIOMotorDatabase,
        user: AppUser,
        version_id: str,
    ) -> bool:
        coll = await cls.get_profiles_coll(db)
        res = await coll.update_one(
            {"user_id": user.id},
            {"$pull": {"resume_versions": {"url": {"$regex": version_id}}}},
        )
        return res.modified_count > 0
