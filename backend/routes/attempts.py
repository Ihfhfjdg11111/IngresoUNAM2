"""
Exam attempts routes
"""
from typing import List, Dict
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends

from models import AttemptCreate, AttemptResponse, AttemptSubmit, SaveProgressRequest, PracticeAttemptCreate
from utils.database import db
from utils.config import UNAM_EXAM_CONFIG, EXAM_DURATION_MINUTES
from services.attempt_service import AttemptService
from services.subscription_service import SubscriptionService
from routes.auth import get_current_user

router = APIRouter(prefix="/attempts", tags=["Attempts"])


@router.post("", response_model=AttemptResponse)
async def create_attempt(data: AttemptCreate, user: Dict = Depends(get_current_user)):
    """Create a new attempt"""
    simulator = await db.simulators.find_one({"simulator_id": data.simulator_id}, {"_id": 0})
    if not simulator:
        raise HTTPException(status_code=404, detail="Simulator not found")
    
    # Check access
    has_access = await SubscriptionService.check_simulator_access(user, simulator["area"])
    if not has_access:
        from utils.config import FREE_SIMULATORS_PER_AREA
        raise HTTPException(
            status_code=403,
            detail=f"Has alcanzado el límite de {FREE_SIMULATORS_PER_AREA} simulacros gratuitos para esta área. Suscríbete para acceso ilimitado."
        )
    
    # Create attempt
    attempt = await AttemptService.create_attempt(user["user_id"], data.simulator_id, data.question_count)
    
    return AttemptResponse(
        attempt_id=attempt["attempt_id"],
        simulator_id=data.simulator_id,
        simulator_name=simulator["name"],
        user_id=user["user_id"],
        started_at=attempt["started_at"],
        total_questions=attempt["total_questions"],
        status="in_progress"
    )


@router.get("")
async def get_user_attempts(user: Dict = Depends(get_current_user)):
    """Get user's attempts"""
    attempts = await db.attempts.find({"user_id": user["user_id"]}, {"_id": 0}).sort("started_at", -1).to_list(100)
    result = []
    for a in attempts:
        simulator = await db.simulators.find_one({"simulator_id": a["simulator_id"]}, {"_id": 0})
        result.append({
            "attempt_id": a["attempt_id"],
            "simulator_id": a["simulator_id"],
            "simulator_name": simulator["name"] if simulator else "Unknown",
            "user_id": a["user_id"],
            "started_at": a["started_at"],
            "finished_at": a.get("finished_at"),
            "score": a.get("score"),
            "total_questions": a.get("total_questions", 120),
            "status": a["status"],
            "saved_progress": a.get("saved_progress")
        })
    return result


@router.get("/{attempt_id}")
async def get_attempt_detail(attempt_id: str, user: Dict = Depends(get_current_user)):
    """Get attempt details"""
    attempt = await db.attempts.find_one({"attempt_id": attempt_id, "user_id": user["user_id"]}, {"_id": 0})
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    
    simulator = await db.simulators.find_one({"simulator_id": attempt["simulator_id"]}, {"_id": 0})
    
    return {
        "attempt_id": attempt["attempt_id"],
        "simulator_id": attempt["simulator_id"],
        "simulator_name": simulator["name"] if simulator else "Unknown",
        "status": attempt["status"],
        "started_at": attempt["started_at"],
        "total_questions": attempt.get("total_questions", 120),
        "duration_minutes": attempt.get("duration_minutes", EXAM_DURATION_MINUTES),
        "saved_progress": attempt.get("saved_progress"),
        "score": attempt.get("score"),
        "answers": attempt.get("answers", [])
    }


@router.get("/{attempt_id}/questions")
async def get_attempt_questions(attempt_id: str, user: Dict = Depends(get_current_user)):
    """Get questions for an attempt (for resuming)"""
    attempt = await db.attempts.find_one({"attempt_id": attempt_id, "user_id": user["user_id"]}, {"_id": 0})
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    
    simulator = await db.simulators.find_one({"simulator_id": attempt["simulator_id"]}, {"_id": 0})
    if not simulator:
        raise HTTPException(status_code=404, detail="Simulator not found")
    
    area_config = UNAM_EXAM_CONFIG.get(simulator["area"], {})
    question_ids = attempt.get("question_ids", [])
    
    if not question_ids:
        raise HTTPException(status_code=400, detail="No questions found for this attempt")
    
    # Fetch questions in order
    questions = []
    reading_texts_cache = {}
    
    for qid in question_ids:
        q = await db.questions.find_one({"question_id": qid}, {"_id": 0})
        if not q:
            continue
        
        subject = await db.subjects.find_one({"subject_id": q["subject_id"]}, {"_id": 0})
        
        # Fetch reading text
        reading_text_content = None
        if q.get("reading_text_id"):
            if q["reading_text_id"] not in reading_texts_cache:
                rt = await db.reading_texts.find_one({"reading_text_id": q["reading_text_id"]}, {"_id": 0})
                reading_texts_cache[q["reading_text_id"]] = rt["content"] if rt else None
            reading_text_content = reading_texts_cache.get(q["reading_text_id"])
        
        questions.append({
            "question_id": q["question_id"],
            "subject_id": q["subject_id"],
            "subject_name": subject["name"] if subject else "Unknown",
            "topic": q["topic"],
            "text": q["text"],
            "options": q["options"],
            "image_url": q.get("image_url"),
            "option_images": q.get("option_images"),
            "reading_text": reading_text_content
        })
    
    return {
        "simulator": {
            "simulator_id": simulator["simulator_id"],
            "name": simulator["name"],
            "area": simulator["area"],
            "area_name": area_config.get("name", "Unknown"),
            "duration_minutes": attempt.get("duration_minutes", EXAM_DURATION_MINUTES)
        },
        "questions": questions,
        "total_questions": len(questions),
        "saved_progress": attempt.get("saved_progress")
    }


@router.post("/{attempt_id}/save-progress")
async def save_attempt_progress(attempt_id: str, data: SaveProgressRequest, user: Dict = Depends(get_current_user)):
    """Save attempt progress"""
    attempt = await db.attempts.find_one({"attempt_id": attempt_id, "user_id": user["user_id"]}, {"_id": 0})
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt["status"] == "completed":
        raise HTTPException(status_code=400, detail="Cannot save progress on completed attempt")
    
    answers_data = [{"question_id": a.question_id, "selected_option": a.selected_option} for a in data.answers]
    
    await db.attempts.update_one(
        {"attempt_id": attempt_id},
        {"$set": {
            "saved_progress": {
                "current_question": data.current_question,
                "time_remaining": data.time_remaining,
                "answers": answers_data
            }
        }}
    )
    
    return {"message": "Progress saved", "saved_at": datetime.now(timezone.utc).isoformat()}


@router.post("/{attempt_id}/submit")
async def submit_attempt(attempt_id: str, data: AttemptSubmit, user: Dict = Depends(get_current_user)):
    """Submit an attempt"""
    attempt = await db.attempts.find_one({"attempt_id": attempt_id, "user_id": user["user_id"]}, {"_id": 0})
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt["status"] == "completed":
        raise HTTPException(status_code=400, detail="Already completed")
    
    if len(data.answers) == 0:
        raise HTTPException(status_code=400, detail="No answers provided")
    
    simulator = await db.simulators.find_one({"simulator_id": attempt["simulator_id"]}, {"_id": 0})
    area_config = UNAM_EXAM_CONFIG.get(simulator["area"], {})
    
    now = datetime.now(timezone.utc)
    
    # Calculate actual time taken based on time remaining (not total elapsed time)
    # This accounts for pauses/breaks during the exam
    duration_minutes = attempt.get("duration_minutes", 180)
    saved_progress = attempt.get("saved_progress", {})
    time_remaining = saved_progress.get("time_remaining", duration_minutes * 60)
    
    # Convert time_remaining from seconds to minutes and calculate actual time used
    time_taken = duration_minutes - (time_remaining / 60)
    
    # Ensure time_taken is positive and reasonable
    if time_taken < 0:
        time_taken = 0
    if time_taken > duration_minutes:
        time_taken = duration_minutes
    
    total_score = 0
    subject_scores = {}
    answers_data = []
    
    for answer in data.answers:
        question = await db.questions.find_one({"question_id": answer.question_id}, {"_id": 0})
        if not question:
            continue
        
        # Handle case where selected_option might be None/invalid
        if answer.selected_option is None or answer.selected_option < 0 or answer.selected_option > 3:
            is_correct = False
        else:
            is_correct = question["correct_answer"] == answer.selected_option
        if is_correct:
            total_score += 1
        
        subject = await db.subjects.find_one({"subject_id": question["subject_id"]}, {"_id": 0})
        subject_name = subject["name"] if subject else "Unknown"
        
        if subject_name not in subject_scores:
            subject_scores[subject_name] = {"correct": 0, "total": 0}
        subject_scores[subject_name]["total"] += 1
        if is_correct:
            subject_scores[subject_name]["correct"] += 1
        
        answers_data.append({
            "question_id": answer.question_id,
            "selected_option": answer.selected_option,
            "correct_answer": question["correct_answer"],
            "is_correct": is_correct,
            "subject_name": subject_name,
            "explanation": question["explanation"],
            "question_text": question["text"],
            "options": question["options"]
        })
    
    await db.attempts.update_one(
        {"attempt_id": attempt_id},
        {"$set": {
            "finished_at": now.isoformat(),
            "score": total_score,
            "status": "completed",
            "answers": answers_data,
            "subject_scores": subject_scores,
            "time_taken_minutes": int(time_taken)
        }}
    )
    
    return {
        "attempt_id": attempt_id,
        "simulator_id": attempt["simulator_id"],
        "simulator_name": simulator["name"],
        "area": simulator["area"],
        "area_name": area_config.get("name", "Unknown"),
        "user_id": user["user_id"],
        "started_at": attempt["started_at"],
        "finished_at": now.isoformat(),
        "score": total_score,
        "total_questions": len(data.answers),
        "percentage": round((total_score / len(data.answers)) * 100, 2) if data.answers else 0,
        "time_taken_minutes": int(time_taken),
        "subject_scores": subject_scores
    }


@router.get("/{attempt_id}/results")
async def get_attempt_results(attempt_id: str, user: Dict = Depends(get_current_user)):
    """Get attempt results"""
    attempt = await db.attempts.find_one({
        "attempt_id": attempt_id,
        "user_id": user["user_id"],
        "status": "completed"
    }, {"_id": 0})
    
    if not attempt:
        raise HTTPException(status_code=404, detail="Completed attempt not found")
    
    simulator = await db.simulators.find_one({"simulator_id": attempt["simulator_id"]}, {"_id": 0})
    area_config = UNAM_EXAM_CONFIG.get(simulator["area"], {})
    
    # Calculate actual time taken based on saved value or compute it
    # Use saved time_taken_minutes if available (calculated based on time remaining)
    if "time_taken_minutes" in attempt:
        time_taken_minutes = attempt["time_taken_minutes"]
    else:
        # Fallback for old attempts: calculate based on duration - time_remaining
        duration_minutes = attempt.get("duration_minutes", 180)
        saved_progress = attempt.get("saved_progress", {})
        time_remaining = saved_progress.get("time_remaining", duration_minutes * 60)
        time_taken_minutes = int(duration_minutes - (time_remaining / 60))
        if time_taken_minutes < 0:
            time_taken_minutes = 0
    
    # Enrich answers with reading texts
    enriched_answers = []
    reading_texts_cache = {}
    
    for answer in attempt.get("answers", []):
        question = await db.questions.find_one({"question_id": answer["question_id"]}, {"_id": 0})
        reading_text = None
        
        if question and question.get("reading_text_id"):
            if question["reading_text_id"] not in reading_texts_cache:
                rt = await db.reading_texts.find_one({"reading_text_id": question["reading_text_id"]}, {"_id": 0})
                reading_texts_cache[question["reading_text_id"]] = rt["content"] if rt else None
            reading_text = reading_texts_cache.get(question["reading_text_id"])
        
        enriched_answers.append({
            **answer,
            "reading_text": reading_text,
            "topic": question.get("topic") if question else None,
            "image_url": question.get("image_url") if question else None
        })
    
    return {
        "attempt_id": attempt_id,
        "simulator_id": attempt["simulator_id"],
        "simulator_name": simulator["name"],
        "area": simulator["area"],
        "area_name": area_config.get("name", "Unknown"),
        "user_id": user["user_id"],
        "started_at": attempt["started_at"],
        "finished_at": attempt["finished_at"],
        "score": attempt["score"],
        "total_questions": len(attempt.get("answers", [])),
        "percentage": round((attempt["score"] / len(attempt.get("answers", []))) * 100, 2) if attempt.get("answers") else 0,
        "time_taken_minutes": time_taken_minutes,
        "subject_scores": attempt.get("subject_scores", {}),
        "answers": enriched_answers
    }


@router.post("/{attempt_id}/abandon")
async def abandon_attempt(attempt_id: str, user: Dict = Depends(get_current_user)):
    """Abandon an in-progress attempt and mark it as completed with partial answers"""
    attempt = await db.attempts.find_one({"attempt_id": attempt_id, "user_id": user["user_id"]})
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    
    if attempt["status"] != "in_progress":
        raise HTTPException(status_code=400, detail="Attempt is not in progress")
    
    # Get saved progress (answers already submitted)
    saved_progress = attempt.get("saved_progress", {})
    saved_answers = saved_progress.get("answers", [])
    
    if not saved_answers:
        # If no answers, just mark as abandoned
        await db.attempts.update_one(
            {"attempt_id": attempt_id},
            {
                "$set": {
                    "status": "abandoned",
                    "abandoned_at": datetime.now(timezone.utc)
                }
            }
        )
        return {"message": "Attempt abandoned - no answers to save"}
    
    # Calculate score with the answers the user already gave
    total_score = 0
    subject_scores = {}
    answers_data = []
    
    for answer in saved_answers:
        question = await db.questions.find_one({"question_id": answer["question_id"]}, {"_id": 0})
        if not question:
            continue
        
        # Check if answer is correct
        selected_option = answer.get("selected_option")
        if selected_option is not None and selected_option >= 0 and selected_option <= 3:
            is_correct = question["correct_answer"] == selected_option
        else:
            is_correct = False
            
        if is_correct:
            total_score += 1
            
        # Track subject scores
        subject = await db.subjects.find_one({"subject_id": question["subject_id"]}, {"_id": 0})
        if subject:
            subject_name = subject["name"]
            if subject_name not in subject_scores:
                subject_scores[subject_name] = {"correct": 0, "total": 0}
            subject_scores[subject_name]["total"] += 1
            if is_correct:
                subject_scores[subject_name]["correct"] += 1
        
        answers_data.append({
            "question_id": answer["question_id"],
            "selected_option": selected_option,
            "is_correct": is_correct,
            "correct_answer": question["correct_answer"]
        })
    
    # Calculate time taken
    now = datetime.now(timezone.utc)
    started_at = attempt.get("started_at")
    if isinstance(started_at, str):
        started_at = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    time_taken_minutes = (now - started_at).total_seconds() / 60 if started_at else 0
    
    # Mark as completed with partial results
    await db.attempts.update_one(
        {"attempt_id": attempt_id},
        {
            "$set": {
                "status": "completed",
                "finished_at": now,
                "score": total_score,
                "total_questions": attempt.get("total_questions", len(saved_answers)),
                "answers": answers_data,
                "subject_scores": subject_scores,
                "time_taken_minutes": time_taken_minutes,
                "completed_partially": True  # Flag to indicate this was auto-completed
            }
        }
    )
    
    return {
        "message": "Attempt marked as completed with partial answers",
        "score": total_score,
        "total_questions": len(saved_answers),
        "percentage": round((total_score / len(saved_answers)) * 100, 2) if saved_answers else 0
    }
