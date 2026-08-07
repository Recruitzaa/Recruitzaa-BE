from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4
from pydantic import Field

from shared.utils.serialization import CamelModel
from .application import Application, ApplicationStage

class KanbanCard(CamelModel):
    id: str
    job_id: str
    job_title: str
    company: str
    stage: ApplicationStage
    applied_at: Optional[datetime] = None
    ai_match_score: Optional[int] = None
    position: int = 0

class KanbanBoardResponse(CamelModel):
    saved: list[KanbanCard] = Field(default_factory=list)
    applied: list[KanbanCard] = Field(default_factory=list)
    screening: list[KanbanCard] = Field(default_factory=list)
    interview: list[KanbanCard] = Field(default_factory=list)
    offer: list[KanbanCard] = Field(default_factory=list)
    rejected: list[KanbanCard] = Field(default_factory=list)
