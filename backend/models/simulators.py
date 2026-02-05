"""
Pydantic models for simulators
"""
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator
from utils import sanitize_string
from utils.config import MAX_NAME_LENGTH, UNAM_EXAM_CONFIG


class SimulatorCreate(BaseModel):
    name: str
    area: str
    description: Optional[str] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        sanitized = sanitize_string(v, MAX_NAME_LENGTH)
        if not sanitized:
            raise ValueError('Name is required')
        return sanitized

    @field_validator('area')
    @classmethod
    def validate_area(cls, v):
        if v not in UNAM_EXAM_CONFIG:
            raise ValueError('Invalid area')
        return v


class SimulatorResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    simulator_id: str
    name: str
    area: str
    area_name: str
    area_color: str
    description: Optional[str] = None
    total_questions: int
    duration_minutes: int
    created_at: str
