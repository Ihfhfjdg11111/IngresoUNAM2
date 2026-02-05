"""
Question reports routes
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends

from models import QuestionReportCreate
from utils.database import db
from routes.auth import get_current_user

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post("")
async def create_report(data: QuestionReportCreate, user: dict = Depends(get_current_user)):
    """Report a question with an issue"""
    question = await db.questions.find_one({"question_id": data.question_id}, {"_id": 0})
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    report_id = f"report_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    
    await db.question_reports.insert_one({
        "report_id": report_id,
        "question_id": data.question_id,
        "user_id": user["user_id"],
        "reason": data.reason,
        "details": data.details,
        "status": "pending",
        "created_at": now
    })
    
    return {"message": "Reporte enviado", "report_id": report_id}
