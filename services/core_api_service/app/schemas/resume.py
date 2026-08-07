from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from shared.utils.serialization import CamelModel

class GenerateLatexRequest(CamelModel):
    template_id: str = Field("jakes-resume", description="Target LaTeX template ID")
    custom_profile: Optional[Dict[str, Any]] = Field(None, description="Optional override profile data")

class SaveResumeRequest(CamelModel):
    title: str = Field(..., description="User-given name for the resume")
    template_id: str = Field("jakes-resume", description="LaTeX template ID")
    latex_code: str = Field(..., description="LaTeX source code")

class ResumeTemplateResponse(CamelModel):
    id: str
    name: str
    category: str
    tag: str
    description: str
    accent_color: str

class GenerateLatexResponse(CamelModel):
    template_id: str
    template_name: str
    latex_code: str
    suggested_filename: str

class SavedResumeResponse(CamelModel):
    id: str
    user_id: str
    title: str
    template_id: str
    latex_code: str
    created_at: str
    updated_at: str
