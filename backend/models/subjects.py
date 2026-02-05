"""
Pydantic models for subjects
"""
from pydantic import BaseModel, ConfigDict


class SubjectResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    subject_id: str
    name: str
    slug: str
    question_count: int
