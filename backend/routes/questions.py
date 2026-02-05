"""
Questions routes (admin only for modifications)
"""
from typing import List, Optional, Dict
from fastapi import APIRouter, HTTPException, Depends

from models import QuestionResponse
from utils.database import db
from routes.auth import get_current_user, get_admin_user

router = APIRouter(prefix="/questions", tags=["Questions"])


@router.get("", response_model=List[QuestionResponse])
async def get_questions(subject_id: Optional[str] = None, limit: int = 100, user: Dict = Depends(get_current_user)):
    """Get questions (admin sees correct answers)"""
    query = {"subject_id": subject_id} if subject_id else {}
    limit = min(limit, 500)
    
    questions = await db.questions.find(query, {"_id": 0}).to_list(limit)
    result = []
    reading_texts_cache = {}
    
    for q in questions:
        subject = await db.subjects.find_one({"subject_id": q["subject_id"]}, {"_id": 0})
        
        # Fetch reading text if exists
        reading_text_content = None
        if q.get("reading_text_id"):
            if q["reading_text_id"] not in reading_texts_cache:
                rt = await db.reading_texts.find_one({"reading_text_id": q["reading_text_id"]}, {"_id": 0})
                reading_texts_cache[q["reading_text_id"]] = rt["content"] if rt else None
            reading_text_content = reading_texts_cache.get(q["reading_text_id"])
        
        # Only show correct answer/explanation to admin
        is_admin = user.get("role") == "admin"
        
        result.append(QuestionResponse(
            question_id=q["question_id"],
            subject_id=q["subject_id"],
            subject_name=subject["name"] if subject else "Unknown",
            topic=q["topic"],
            text=q["text"],
            options=q["options"],
            correct_answer=q["correct_answer"] if is_admin else None,
            explanation=q["explanation"] if is_admin else None,
            image_url=q.get("image_url"),
            option_images=q.get("option_images"),
            reading_text_id=q.get("reading_text_id"),
            reading_text=reading_text_content if is_admin else None
        ))
    
    return result
