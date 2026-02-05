"""
Feedback routes - User feedback and suggestions
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from utils.database import db
from routes.auth import get_current_user, get_admin_user

router = APIRouter(prefix="/feedback", tags=["Feedback"])


class FeedbackCreate(BaseModel):
    type: str  # 'bug', 'feature', 'improvement', 'other'
    message: str
    page: Optional[str] = None


class FeedbackResponse(BaseModel):
    feedback_id: str
    type: str
    message: str
    status: str
    created_at: str


@router.post("", response_model=FeedbackResponse)
async def submit_feedback(
    feedback: FeedbackCreate,
    user: dict = Depends(get_current_user)
):
    """Submit user feedback"""
    if not feedback.message or len(feedback.message.strip()) < 5:
        raise HTTPException(status_code=400, detail="El mensaje debe tener al menos 5 caracteres")
    
    if feedback.type not in ['bug', 'feature', 'improvement', 'other']:
        raise HTTPException(status_code=400, detail="Tipo de feedback inválido")
    
    import uuid
    feedback_doc = {
        "feedback_id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        "user_email": user.get("email"),
        "user_name": user.get("name"),
        "type": feedback.type,
        "message": feedback.message.strip(),
        "page": feedback.page,
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    await db.feedback.insert_one(feedback_doc)
    
    return FeedbackResponse(
        feedback_id=feedback_doc["feedback_id"],
        type=feedback_doc["type"],
        message=feedback_doc["message"],
        status=feedback_doc["status"],
        created_at=feedback_doc["created_at"].isoformat()
    )


@router.get("/my")
async def get_my_feedback(user: dict = Depends(get_current_user)):
    """Get current user's feedback history"""
    feedbacks = await db.feedback.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    for f in feedbacks:
        if isinstance(f.get("created_at"), datetime):
            f["created_at"] = f["created_at"].isoformat()
    
    return feedbacks


@router.get("/admin/all")
async def get_all_feedback(
    status: Optional[str] = None,
    type: Optional[str] = None,
    user: dict = Depends(get_admin_user)
):
    """Get all feedback (admin only)"""
    query = {}
    if status:
        query["status"] = status
    if type:
        query["type"] = type
    
    feedbacks = await db.feedback.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    
    for f in feedbacks:
        if isinstance(f.get("created_at"), datetime):
            f["created_at"] = f["created_at"].isoformat()
        if isinstance(f.get("updated_at"), datetime):
            f["updated_at"] = f["updated_at"].isoformat()
    
    return feedbacks


@router.put("/admin/{feedback_id}/status")
async def update_feedback_status(
    feedback_id: str,
    status_update: dict,
    user: dict = Depends(get_admin_user)
):
    """Update feedback status (admin only)"""
    if status_update.get("status") not in ["pending", "in_progress", "resolved", "rejected"]:
        raise HTTPException(status_code=400, detail="Estado inválido")
    
    result = await db.feedback.update_one(
        {"feedback_id": feedback_id},
        {
            "$set": {
                "status": status_update["status"],
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Feedback no encontrado")
    
    return {"message": "Estado actualizado"}
