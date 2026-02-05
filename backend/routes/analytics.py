"""
Analytics routes
"""
from typing import Dict, List, Any
from fastapi import APIRouter, Depends

from models import ProgressResponse
from utils.database import db
from utils.config import UNAM_EXAM_CONFIG
from routes.auth import get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/student/performance")
async def get_student_analytics(user: Dict = Depends(get_current_user)):
    """Get detailed analytics for student improvement"""
    attempts = await db.attempts.find(
        {"user_id": user["user_id"], "status": "completed"},
        {"_id": 0}
    ).to_list(1000)
    
    if not attempts:
        return {
            "total_attempts": 0,
            "total_questions_answered": 0,
            "overall_accuracy": 0,
            "subject_performance": {},
            "progress_trend": [],
            "weak_subjects": [],
            "strong_subjects": [],
            "recommendations": ["Comienza tu primer simulacro para ver tus estadísticas"]
        }
    
    # Pre-load subject names
    subjects_cursor = await db.subjects.find({}, {"_id": 0, "subject_id": 1, "name": 1}).to_list(100)
    subject_names_map = {s["subject_id"]: s["name"] for s in subjects_cursor}
    
    # Subject performance aggregation
    subject_stats = {}
    progress_data = []
    
    for attempt in sorted(attempts, key=lambda x: x["started_at"]):
        for answer in attempt.get("answers", []):
            subject = answer.get("subject_name")
            if not subject or subject == "Unknown":
                subject_id = answer.get("subject_id")
                subject = subject_names_map.get(subject_id, "Unknown")
            
            if subject == "Unknown":
                continue
            
            if subject not in subject_stats:
                subject_stats[subject] = {"correct": 0, "total": 0}
            subject_stats[subject]["total"] += 1
            if answer.get("is_correct"):
                subject_stats[subject]["correct"] += 1
        
        total = len(attempt.get("answers", []))
        if total > 0:
            progress_data.append({
                "date": attempt["started_at"],
                "score": attempt.get("score", 0),
                "total": total,
                "percentage": round((attempt.get("score", 0) / total) * 100, 1)
            })
    
    # Calculate performance percentages
    subject_performance = {}
    weak_subjects = []
    strong_subjects = []
    
    for subject, stats in subject_stats.items():
        if stats["total"] > 0:
            pct = round((stats["correct"] / stats["total"]) * 100, 1)
            subject_performance[subject] = {
                "correct": stats["correct"],
                "total": stats["total"],
                "percentage": pct
            }
            if pct < 60:
                weak_subjects.append({"subject": subject, "percentage": pct})
            elif pct >= 80:
                strong_subjects.append({"subject": subject, "percentage": pct})
    
    weak_subjects.sort(key=lambda x: x["percentage"])
    strong_subjects.sort(key=lambda x: x["percentage"], reverse=True)
    
    # Generate recommendations
    recommendations = []
    if weak_subjects:
        recommendations.append(f"Enfócate en mejorar {weak_subjects[0]['subject']} ({weak_subjects[0]['percentage']}%)")
    if len(attempts) < 3:
        recommendations.append("Realiza más simulacros para obtener estadísticas más precisas")
    if progress_data and len(progress_data) >= 2:
        recent = progress_data[-1]["percentage"]
        previous = progress_data[-2]["percentage"]
        if recent > previous:
            recommendations.append(f"¡Excelente! Mejoraste {round(recent - previous, 1)}% en tu último intento")
        elif recent < previous:
            recommendations.append("Tu último resultado bajó. Revisa las materias donde fallaste")
    
    total_correct = sum(s["correct"] for s in subject_stats.values())
    total_answered = sum(s["total"] for s in subject_stats.values())
    
    return {
        "total_attempts": len(attempts),
        "total_questions_answered": total_answered,
        "overall_accuracy": round((total_correct / total_answered) * 100, 1) if total_answered > 0 else 0,
        "subject_performance": subject_performance,
        "progress_trend": progress_data[-10:],
        "weak_subjects": weak_subjects[:3],
        "strong_subjects": strong_subjects[:3],
        "recommendations": recommendations[:5]
    }


@router.get("/progress", response_model=ProgressResponse)
async def get_user_progress(user: Dict = Depends(get_current_user)):
    """Get user progress summary"""
    attempts = await db.attempts.find(
        {"user_id": user["user_id"], "status": "completed"},
        {"_id": 0}
    ).to_list(1000)
    
    if not attempts:
        return ProgressResponse(
            total_attempts=0,
            average_score=0,
            best_score=0,
            total_questions_answered=0,
            area_stats={},
            recent_attempts=[]
        )
    
    total_score = sum(a.get("score", 0) for a in attempts)
    total_questions = sum(len(a.get("answers", [])) for a in attempts)
    best_score = max((a.get("score", 0) for a in attempts), default=0)
    
    area_stats = {}
    for attempt in attempts:
        simulator = await db.simulators.find_one({"simulator_id": attempt["simulator_id"]}, {"_id": 0})
        if not simulator:
            continue
        area = simulator["area"]
        if area not in area_stats:
            area_config = UNAM_EXAM_CONFIG.get(area, {})
            area_stats[area] = {
                "name": area_config.get("name", "Unknown"),
                "color": area_config.get("color", "#666"),
                "attempts": 0,
                "average_score": 0,
                "best_score": 0,
                "total_score": 0
            }
        area_stats[area]["attempts"] += 1
        area_stats[area]["total_score"] += attempt.get("score", 0)
        area_stats[area]["best_score"] = max(area_stats[area]["best_score"], attempt.get("score", 0))
    
    for area in area_stats:
        if area_stats[area]["attempts"] > 0:
            area_stats[area]["average_score"] = round(
                area_stats[area]["total_score"] / area_stats[area]["attempts"], 1
            )
    
    recent = sorted(attempts, key=lambda x: x["started_at"], reverse=True)[:5]
    recent_attempts = []
    for a in recent:
        simulator = await db.simulators.find_one({"simulator_id": a["simulator_id"]}, {"_id": 0})
        recent_attempts.append({
            "attempt_id": a["attempt_id"],
            "simulator_name": simulator["name"] if simulator else "Unknown",
            "score": a.get("score", 0),
            "total": len(a.get("answers", [])),
            "date": a["started_at"]
        })
    
    return ProgressResponse(
        total_attempts=len(attempts),
        average_score=round(total_score / len(attempts), 1),
        best_score=best_score,
        total_questions_answered=total_questions,
        area_stats=area_stats,
        recent_attempts=recent_attempts
    )
