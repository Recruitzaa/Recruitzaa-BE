from typing import Optional
from pydantic import Field
from shared.utils.serialization import CamelModel
from ..models.application import ApplicationStage

class ApplyJobRequest(CamelModel):
    resume_url: Optional[str] = None
    cover_letter: Optional[str] = None

class UpdateApplicationStageRequest(CamelModel):
    stage: ApplicationStage

class SaveJobRequest(CamelModel):
    job_id: str

class ApplicationNoteRequest(CamelModel):
    note: str
