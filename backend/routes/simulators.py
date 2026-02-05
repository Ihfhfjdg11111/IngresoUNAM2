"""
Simulators routes
"""
from datetime import datetime, timezone
from typing import List, Dict
from fastapi import APIRouter, HTTPException, Depends

from models import SimulatorResponse
from utils.database import db
from utils.config import UNAM_EXAM_CONFIG, TOTAL_QUESTIONS, EXAM_DURATION_MINUTES
from routes.auth import get_current_user

router = APIRouter(prefix="/simulators", tags=["Simulators"])


@router.get("", response_model=List[SimulatorResponse])
async def get_simulators():
    """Get all simulators"""
    simulators = await db.simulators.find({}, {"_id": 0}).to_list(100)
    return [SimulatorResponse(
        simulator_id=s["simulator_id"],
        name=s["name"],
        area=s["area"],
        area_name=UNAM_EXAM_CONFIG.get(s["area"], {}).get("name", "Unknown"),
        area_color=UNAM_EXAM_CONFIG.get(s["area"], {}).get("color", "#666"),
        description=s.get("description"),
        total_questions=TOTAL_QUESTIONS,
        duration_minutes=EXAM_DURATION_MINUTES,
        created_at=s.get("created_at", datetime.now(timezone.utc).isoformat())
    ) for s in simulators]


@router.get("/{simulator_id}/questions")
async def get_simulator_questions(
    simulator_id: str,
    question_count: int = 120,
    user: Dict = Depends(get_current_user)
):
    """Generate questions for a simulator"""
    from services.attempt_service import AttemptService
    
    simulator = await db.simulators.find_one({"simulator_id": simulator_id}, {"_id": 0})
    if not simulator:
        raise HTTPException(status_code=404, detail="Simulator not found")
    
    # Validate question count
    if question_count not in [40, 80, 120]:
        question_count = 120
    
    # Generate questions
    questions = await AttemptService.generate_attempt_questions(simulator["area"], question_count)
    
    # Fetch reading texts
    reading_texts = await AttemptService.get_reading_texts_for_questions(questions)
    for q in questions:
        if q.get("reading_text_id"):
            q["reading_text"] = reading_texts.get(q["reading_text_id"])
    
    duration_minutes = int(len(questions) * 1.5)
    
    return {
        "simulator": {
            "simulator_id": simulator["simulator_id"],
            "name": simulator["name"],
            "area": simulator["area"],
            "area_name": UNAM_EXAM_CONFIG.get(simulator["area"], {}).get("name", "Unknown"),
            "duration_minutes": duration_minutes
        },
        "questions": questions,
        "total_questions": len(questions)
    }
