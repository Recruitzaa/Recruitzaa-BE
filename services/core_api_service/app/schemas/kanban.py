from pydantic import Field
from shared.utils.serialization import CamelModel
from ..models.application import ApplicationStage

class MoveKanbanCardRequest(CamelModel):
    application_id: str
    to_stage: ApplicationStage
    position: int = 0
