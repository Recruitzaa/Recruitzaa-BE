import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Any
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase
from shared.messaging.kafka_producer import get_producer
from shared.messaging.topics import JOB_CREATED
from shared.utils.pagination import paginate, get_skip
from shared.utils.serialization import PaginatedResponse
from ..models.job import Job, JobStatus
from ..schemas.jobs import CreateJobRequest, UpdateJobRequest, JobFilterParams

logger = logging.getLogger(__name__)


class JobService:
    @staticmethod
    async def get_jobs_collection(db: AsyncIOMotorDatabase):
        return db["jobs"]

    @staticmethod
    async def get_applications_collection(db: AsyncIOMotorDatabase):
        return db["applications"]

    @classmethod
    async def search_jobs(
        cls,
        db: AsyncIOMotorDatabase,
        params: JobFilterParams,
        user_id: Optional[str] = None,
    ) -> PaginatedResponse:
        coll = await cls.get_jobs_collection(db)
        query: dict[str, Any] = {"status": {"$in": [JobStatus.APPROVED.value, "APPROVED"]}}

        if params.keyword:
            query["$or"] = [
                {"title": {"$regex": params.keyword, "$options": "i"}},
                {"description": {"$regex": params.keyword, "$options": "i"}},
                {"company": {"$regex": params.keyword, "$options": "i"}},
                {"tags": {"$regex": params.keyword, "$options": "i"}},
                {"skills_required": {"$regex": params.keyword, "$options": "i"}},
            ]

        if params.location:
            query["location"] = {"$regex": params.location, "$options": "i"}

        if params.job_type:
            query["job_type"] = params.job_type.upper()

        if params.work_mode:
            query["work_mode"] = params.work_mode.upper()

        if params.min_salary is not None:
            query["$or"] = [
                {"salary_min": {"$gte": params.min_salary}},
                {"salary_max": {"$gte": params.min_salary}},
            ]

        if params.posted_within:
            since = datetime.now(timezone.utc) - timedelta(days=params.posted_within)
            query["posted_at"] = {"$gte": since}

        total = await coll.count_documents(query)
        skip = get_skip(params.page, params.page_size)
        cursor = coll.find(query).sort("posted_at", -1).skip(skip).limit(params.page_size)
        docs = await cursor.to_list(length=params.page_size)

        # Build job objects
        jobs = []
        user_apps_map = {}
        if user_id:
            apps_coll = await cls.get_applications_collection(db)
            user_apps = await apps_coll.find({"candidate_id": user_id}).to_list(length=500)
            for app in user_apps:
                user_apps_map[app["job_id"]] = app

        for doc in docs:
            doc_id = str(doc.get("_id"))
            doc["id"] = doc_id
            job = Job.model_validate(doc)
            
            if user_id and doc_id in user_apps_map:
                app_record = user_apps_map[doc_id]
                job.is_saved = app_record.get("stage") == "SAVED"
                job.application_status = app_record.get("stage")
                job.ai_match_score = app_record.get("ai_match_score")
            
            jobs.append(job)

        return paginate(items=jobs, total=total, page=params.page_size and params.page or 1, page_size=params.page_size)

    @classmethod
    async def get_job_by_id(
        cls,
        db: AsyncIOMotorDatabase,
        job_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[Job]:
        coll = await cls.get_jobs_collection(db)
        doc = await coll.find_one({"_id": job_id})
        if not doc:
            return None

        doc["id"] = str(doc.get("_id"))
        job = Job.model_validate(doc)

        if user_id:
            apps_coll = await cls.get_applications_collection(db)
            app_record = await apps_coll.find_one({"job_id": job_id, "candidate_id": user_id})
            if app_record:
                job.is_saved = app_record.get("stage") == "SAVED"
                job.application_status = app_record.get("stage")
                job.ai_match_score = app_record.get("ai_match_score")

        return job

    @classmethod
    async def create_job(
        cls,
        db: AsyncIOMotorDatabase,
        employer_id: str,
        data: CreateJobRequest,
    ) -> Job:
        coll = await cls.get_jobs_collection(db)
        job_id = str(uuid4())
        now = datetime.now(timezone.utc)

        job_dict = {
            "_id": job_id,
            "id": job_id,
            "employer_id": employer_id,
            "company_id": data.company_id,
            "company": data.company,
            "title": data.title,
            "description": data.description,
            "location": data.location,
            "job_type": data.job_type.value if hasattr(data.job_type, "value") else data.job_type,
            "work_mode": data.work_mode.value if hasattr(data.work_mode, "value") else data.work_mode,
            "salary_min": data.salary_min,
            "salary_max": data.salary_max,
            "salary_currency": data.salary_currency,
            "status": JobStatus.APPROVED.value,
            "tags": data.tags,
            "skills_required": data.skills_required,
            "applicants_count": 0,
            "posted_at": now,
            "created_at": now,
            "updated_at": now,
        }

        await coll.insert_one(job_dict)

        # Emit Kafka event
        try:
            producer = await get_producer()
            await producer.send_event(
                JOB_CREATED,
                {
                    "job_id": job_id,
                    "employer_id": employer_id,
                    "title": data.title,
                    "company": data.company,
                },
                key=job_id,
            )
        except Exception as exc:
            logger.warning("Kafka job.created event failed to send: %s", exc)

        return Job.model_validate(job_dict)

    @classmethod
    async def update_job(
        cls,
        db: AsyncIOMotorDatabase,
        job_id: str,
        employer_id: str,
        data: UpdateJobRequest,
    ) -> Optional[Job]:
        coll = await cls.get_jobs_collection(db)
        update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
        if not update_data:
            return await cls.get_job_by_id(db, job_id)

        update_data["updated_at"] = datetime.now(timezone.utc)
        result = await coll.find_one_and_update(
            {"_id": job_id, "employer_id": employer_id},
            {"$set": update_data},
            return_document=True,
        )
        if not result:
            return None
        result["id"] = str(result.get("_id"))
        return Job.model_validate(result)

    @classmethod
    async def delete_job(
        cls,
        db: AsyncIOMotorDatabase,
        job_id: str,
        employer_id: str,
    ) -> bool:
        coll = await cls.get_jobs_collection(db)
        result = await coll.update_one(
            {"_id": job_id, "employer_id": employer_id},
            {"$set": {"status": JobStatus.CLOSED.value, "updated_at": datetime.now(timezone.utc)}},
        )
        return result.modified_count > 0
