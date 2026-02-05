"""
Pydantic models for questions and reading texts
"""
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, field_validator
from utils import sanitize_string, validate_url
from utils.config import MAX_TOPIC_LENGTH, MAX_TEXT_LENGTH, MAX_NAME_LENGTH


class QuestionCreate(BaseModel):
    subject_id: str
    topic: str
    text: str
    options: List[str]
    correct_answer: int
    explanation: str
    image_url: Optional[str] = None
    option_images: Optional[List[Optional[str]]] = None
    reading_text_id: Optional[str] = None

    @field_validator('topic')
    @classmethod
    def validate_topic(cls, v):
        return sanitize_string(v, MAX_TOPIC_LENGTH)

    @field_validator('text')
    @classmethod
    def validate_text(cls, v):
        sanitized = sanitize_string(v, MAX_TEXT_LENGTH)
        if not sanitized:
            raise ValueError('Question text is required')
        return sanitized

    @field_validator('explanation')
    @classmethod
    def validate_explanation(cls, v):
        return sanitize_string(v, MAX_TEXT_LENGTH)

    @field_validator('options')
    @classmethod
    def validate_options(cls, v):
        if len(v) != 4:
            raise ValueError('Exactly 4 options required')
        return [sanitize_string(opt, 1000) for opt in v]

    @field_validator('correct_answer')
    @classmethod
    def validate_correct_answer(cls, v):
        if v < 0 or v > 3:
            raise ValueError('Correct answer must be 0-3')
        return v

    @field_validator('image_url')
    @classmethod
    def validate_image_url(cls, v):
        if v and not validate_url(v):
            raise ValueError('Invalid image URL format')
        return v


class QuestionUpdate(BaseModel):
    subject_id: Optional[str] = None
    topic: Optional[str] = None
    text: Optional[str] = None
    options: Optional[List[str]] = None
    correct_answer: Optional[int] = None
    explanation: Optional[str] = None
    image_url: Optional[str] = None
    option_images: Optional[List[Optional[str]]] = None
    reading_text_id: Optional[str] = None


class QuestionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    question_id: str
    subject_id: str
    subject_name: str
    topic: str
    text: str
    options: List[str]
    correct_answer: Optional[int] = None
    explanation: Optional[str] = None
    image_url: Optional[str] = None
    option_images: Optional[List[Optional[str]]] = None
    reading_text_id: Optional[str] = None
    reading_text: Optional[str] = None


class ReadingTextCreate(BaseModel):
    title: str
    content: str
    subject_id: Optional[str] = None

    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        sanitized = sanitize_string(v, MAX_NAME_LENGTH)
        if not sanitized:
            raise ValueError('Title is required')
        return sanitized

    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        sanitized = sanitize_string(v, 10000)
        if not sanitized:
            raise ValueError('Content is required')
        return sanitized


class ReadingTextResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    reading_text_id: str
    title: str
    content: str
    subject_id: Optional[str] = None
    created_at: str


class BulkQuestionImport(BaseModel):
    questions: List[QuestionCreate]
    reading_texts: Optional[List[ReadingTextCreate]] = None
