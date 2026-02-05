"""
Pydantic models for exam attempts and practice sessions
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, field_validator
from utils import sanitize_string


class AttemptCreate(BaseModel):
    simulator_id: str
    question_count: int = 120

    @field_validator('question_count')
    @classmethod
    def validate_count(cls, v):
        if v not in [40, 80, 120]:
            raise ValueError('Question count must be 40, 80, or 120')
        return v


class PracticeAttemptCreate(BaseModel):
    subject_id: str
    question_count: int = 10

    @field_validator('question_count')
    @classmethod
    def validate_count(cls, v):
        if v < 5 or v > 30:
            raise ValueError('Question count must be between 5 and 30')
        return v


class AnswerSubmit(BaseModel):
    question_id: str
    selected_option: int

    @field_validator('selected_option')
    @classmethod
    def validate_option(cls, v):
        if v < 0 or v > 3:
            raise ValueError('Option must be 0-3')
        return v


class AttemptSubmit(BaseModel):
    answers: List[AnswerSubmit]


class SaveProgressRequest(BaseModel):
    answers: List[AnswerSubmit]
    current_question: int = 0
    time_remaining: int = 0


class AttemptResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    attempt_id: str
    simulator_id: str
    simulator_name: str
    user_id: str
    started_at: str
    finished_at: Optional[str] = None
    score: Optional[int] = None
    total_questions: int
    status: str


class ResultResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    attempt_id: str
    simulator_id: str
    simulator_name: str
    area: str
    area_name: str
    user_id: str
    started_at: str
    finished_at: str
    score: int
    total_questions: int
    percentage: float
    time_taken_minutes: int
    subject_scores: Dict[str, Dict[str, Any]]


class ProgressResponse(BaseModel):
    total_attempts: int
    average_score: float
    best_score: int
    total_questions_answered: int
    area_stats: Dict[str, Dict[str, Any]]
    recent_attempts: List[Dict[str, Any]]


class QuestionReportCreate(BaseModel):
    question_id: str
    reason: str
    details: Optional[str] = None

    @field_validator('reason')
    @classmethod
    def validate_reason(cls, v):
        valid_reasons = ["incorrect_answer", "unclear_text", "wrong_subject", "typo", "other"]
        if v not in valid_reasons:
            raise ValueError('Invalid reason')
        return v

    @field_validator('details')
    @classmethod
    def validate_details(cls, v):
        if v:
            return sanitize_string(v, 500)
        return v
