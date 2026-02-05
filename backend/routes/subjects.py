"""
Subjects routes
"""
from typing import List, Dict
from fastapi import APIRouter, HTTPException, Depends

from models import SubjectResponse
from utils.database import db
from routes.auth import get_current_user

router = APIRouter(prefix="/subjects", tags=["Subjects"])


@router.get("", response_model=List[SubjectResponse])
async def get_subjects(user: Dict = Depends(get_current_user)):
    """Get all subjects with question counts"""
    subjects = await db.subjects.find({}, {"_id": 0}).to_list(100)
    result = []
    for s in subjects:
        count = await db.questions.count_documents({"subject_id": s["subject_id"]})
        result.append(SubjectResponse(
            subject_id=s["subject_id"],
            name=s["name"],
            slug=s["slug"],
            question_count=count
        ))
    return result


@router.get("/{subject_id}")
async def get_subject_detail(subject_id: str):
    """Get subject details including topics"""
    subject = await db.subjects.find_one({"subject_id": subject_id}, {"_id": 0})
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject


@router.get("/{subject_id}/questions")
async def get_subject_questions(subject_id: str, limit: int = 20, user: Dict = Depends(get_current_user)):
    """Get random questions for a subject"""
    subject = await db.subjects.find_one({"subject_id": subject_id}, {"_id": 0})
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Limit to prevent abuse
    limit = min(limit, 50)
    
    questions = await db.questions.aggregate([
        {"$match": {"subject_id": subject_id}},
        {"$sample": {"size": limit}},
        {"$project": {"_id": 0}}
    ]).to_list(limit)
    
    result = []
    for q in questions:
        # Fetch reading text if exists
        reading_text_content = None
        if q.get("reading_text_id"):
            rt = await db.reading_texts.find_one({"reading_text_id": q["reading_text_id"]}, {"_id": 0})
            reading_text_content = rt["content"] if rt else None
        
        result.append({
            "question_id": q["question_id"],
            "subject_id": q["subject_id"],
            "subject_name": subject["name"],
            "topic": q["topic"],
            "text": q["text"],
            "options": q["options"],
            "correct_answer": q["correct_answer"],
            "explanation": q["explanation"],
            "image_url": q.get("image_url"),
            "option_images": q.get("option_images"),
            "reading_text": reading_text_content
        })
    return result
