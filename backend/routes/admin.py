"""
Admin routes
"""
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends

from models import (
    QuestionCreate, QuestionResponse, QuestionUpdate,
    ReadingTextCreate, ReadingTextResponse, BulkQuestionImport,
    SimulatorCreate, SimulatorResponse, RoleUpdateRequest
)
from utils.database import db
from utils.config import UNAM_EXAM_CONFIG, TOTAL_QUESTIONS, EXAM_DURATION_MINUTES, FREE_SIMULATORS_PER_AREA
from utils.security import sanitize_string
from utils.config import MAX_TOPIC_LENGTH, MAX_NAME_LENGTH
from services.auth_service import AuthService
from routes.auth import get_admin_user

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/stats")
async def get_admin_stats(user: dict = Depends(get_admin_user)):
    """Get admin dashboard statistics"""
    total_users = await db.users.count_documents({})
    total_questions = await db.questions.count_documents({})
    total_attempts = await db.attempts.count_documents({})
    completed_attempts = await db.attempts.count_documents({"status": "completed"})
    pending_reports = await db.question_reports.count_documents({"status": "pending"})
    
    # Count premium users with active subscriptions
    # Compare ISO format strings (MongoDB stores as string)
    now_str = datetime.now(timezone.utc).isoformat()
    premium_users = await db.subscriptions.count_documents({
        "status": "active",
        "expires_at": {"$gt": now_str}
    })
    
    recent_attempts = await db.attempts.find(
        {"status": "completed"},
        {"_id": 0, "attempt_id": 1, "user_id": 1, "score": 1, "started_at": 1}
    ).sort("started_at", -1).limit(5).to_list(5)
    
    return {
        "total_users": total_users,
        "premium_users": premium_users,
        "total_questions": total_questions,
        "total_attempts": total_attempts,
        "completed_attempts": completed_attempts,
        "pending_reports": pending_reports,
        "recent_attempts": recent_attempts
    }


@router.get("/stats/detailed")
async def get_admin_stats_detailed(user: dict = Depends(get_admin_user)):
    """Get detailed admin stats including questions per subject"""
    subjects_stats = []
    subjects = await db.subjects.find({}, {"_id": 0}).to_list(100)
    for s in subjects:
        count = await db.questions.count_documents({"subject_id": s["subject_id"]})
        subjects_stats.append({"subject": s["name"], "count": count})
    
    return {
        "total_users": await db.users.count_documents({}),
        "total_questions": await db.questions.count_documents({}),
        "total_simulators": await db.simulators.count_documents({}),
        "total_attempts": await db.attempts.count_documents({"status": "completed"}),
        "total_admins": await db.users.count_documents({"role": "admin"}),
        "questions_per_subject": subjects_stats
    }


# Reading Texts CRUD
@router.post("/reading-texts", response_model=ReadingTextResponse)
async def create_reading_text(data: ReadingTextCreate, user: dict = Depends(get_admin_user)):
    """Create a reading text"""
    reading_text_id = AuthService.generate_id("rt_")
    now = datetime.now(timezone.utc).isoformat()
    
    await db.reading_texts.insert_one({
        "reading_text_id": reading_text_id,
        "title": data.title,
        "content": data.content,
        "subject_id": data.subject_id,
        "created_at": now,
        "created_by": user["user_id"]
    })
    
    return ReadingTextResponse(
        reading_text_id=reading_text_id,
        title=data.title,
        content=data.content,
        subject_id=data.subject_id,
        created_at=now
    )


@router.get("/reading-texts")
async def get_reading_texts(subject_id: Optional[str] = None, user: dict = Depends(get_admin_user)):
    """Get all reading texts"""
    query = {"subject_id": subject_id} if subject_id else {}
    texts = await db.reading_texts.find(query, {"_id": 0}).to_list(500)
    return texts


@router.put("/reading-texts/{reading_text_id}")
async def update_reading_text(reading_text_id: str, data: ReadingTextCreate, user: dict = Depends(get_admin_user)):
    """Update a reading text"""
    existing = await db.reading_texts.find_one({"reading_text_id": reading_text_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Reading text not found")
    
    update_data = {
        "title": sanitize_string(data.title, MAX_TOPIC_LENGTH),
        "content": sanitize_string(data.content, 10000),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    if data.subject_id:
        update_data["subject_id"] = data.subject_id
    
    await db.reading_texts.update_one(
        {"reading_text_id": reading_text_id},
        {"$set": update_data}
    )
    
    updated = await db.reading_texts.find_one({"reading_text_id": reading_text_id}, {"_id": 0})
    return updated


@router.delete("/reading-texts/{reading_text_id}")
async def delete_reading_text(reading_text_id: str, user: dict = Depends(get_admin_user)):
    """Delete a reading text"""
    result = await db.reading_texts.delete_one({"reading_text_id": reading_text_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Reading text not found")
    
    # Remove references from questions
    await db.questions.update_many(
        {"reading_text_id": reading_text_id},
        {"$unset": {"reading_text_id": ""}}
    )
    return {"message": "Reading text deleted"}


# Questions CRUD
@router.post("/questions", response_model=QuestionResponse)
async def create_question(data: QuestionCreate, user: dict = Depends(get_admin_user)):
    """Create a question"""
    subject = await db.subjects.find_one({"subject_id": data.subject_id}, {"_id": 0})
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Validate reading_text_id if provided
    reading_text = None
    if data.reading_text_id:
        reading_text = await db.reading_texts.find_one({"reading_text_id": data.reading_text_id}, {"_id": 0})
        if not reading_text:
            raise HTTPException(status_code=404, detail="Reading text not found")
    
    question_id = AuthService.generate_id("q_")
    question_doc = {
        "question_id": question_id,
        "subject_id": data.subject_id,
        "topic": data.topic,
        "text": data.text,
        "options": data.options,
        "correct_answer": data.correct_answer,
        "explanation": data.explanation,
        "image_url": data.image_url,
        "option_images": data.option_images or [None]*4,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user["user_id"]
    }
    if data.reading_text_id:
        question_doc["reading_text_id"] = data.reading_text_id
    
    await db.questions.insert_one(question_doc)
    
    return QuestionResponse(
        question_id=question_id,
        subject_id=data.subject_id,
        subject_name=subject["name"],
        topic=data.topic,
        text=data.text,
        options=data.options,
        correct_answer=data.correct_answer,
        explanation=data.explanation,
        image_url=data.image_url,
        option_images=data.option_images,
        reading_text_id=data.reading_text_id,
        reading_text=reading_text["content"] if reading_text else None
    )


@router.post("/questions/bulk")
async def bulk_import_questions(data: BulkQuestionImport, user: dict = Depends(get_admin_user)):
    """Import multiple questions at once"""
    imported_questions = 0
    imported_texts = 0
    errors = []
    reading_text_map = {}
    
    # First, import reading texts if provided
    if data.reading_texts:
        for i, rt in enumerate(data.reading_texts):
            try:
                reading_text_id = AuthService.generate_id("rt_")
                await db.reading_texts.insert_one({
                    "reading_text_id": reading_text_id,
                    "title": rt.title,
                    "content": rt.content,
                    "subject_id": rt.subject_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "created_by": user["user_id"]
                })
                reading_text_map[rt.title] = reading_text_id
                imported_texts += 1
            except Exception as e:
                errors.append(f"Reading text {i+1}: {str(e)}")
    
    # Then import questions
    for i, q in enumerate(data.questions):
        try:
            subject = await db.subjects.find_one({"subject_id": q.subject_id}, {"_id": 0})
            if not subject:
                errors.append(f"Question {i+1}: Subject not found")
                continue
            
            question_id = AuthService.generate_id("q_")
            question_doc = {
                "question_id": question_id,
                "subject_id": q.subject_id,
                "topic": q.topic,
                "text": q.text,
                "options": q.options,
                "correct_answer": q.correct_answer,
                "explanation": q.explanation,
                "image_url": q.image_url,
                "option_images": q.option_images or [None]*4,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": user["user_id"]
            }
            
            if q.reading_text_id:
                if q.reading_text_id in reading_text_map:
                    question_doc["reading_text_id"] = reading_text_map[q.reading_text_id]
                else:
                    question_doc["reading_text_id"] = q.reading_text_id
            
            await db.questions.insert_one(question_doc)
            imported_questions += 1
        except Exception as e:
            errors.append(f"Question {i+1}: {str(e)}")
    
    return {
        "imported_questions": imported_questions,
        "imported_reading_texts": imported_texts,
        "errors": errors,
        "total_questions": len(data.questions),
        "total_reading_texts": len(data.reading_texts) if data.reading_texts else 0
    }


@router.put("/questions/{question_id}")
async def update_question(question_id: str, data: QuestionUpdate, user: dict = Depends(get_admin_user)):
    """Update a question"""
    question = await db.questions.find_one({"question_id": question_id}, {"_id": 0})
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    update_data["updated_by"] = user["user_id"]
    
    await db.questions.update_one({"question_id": question_id}, {"$set": update_data})
    
    updated = await db.questions.find_one({"question_id": question_id}, {"_id": 0})
    subject = await db.subjects.find_one({"subject_id": updated["subject_id"]}, {"_id": 0})
    
    return {
        "question_id": updated["question_id"],
        "subject_id": updated["subject_id"],
        "subject_name": subject["name"] if subject else "Unknown",
        "topic": updated["topic"],
        "text": updated["text"],
        "options": updated["options"],
        "correct_answer": updated["correct_answer"],
        "explanation": updated["explanation"],
        "image_url": updated.get("image_url"),
        "option_images": updated.get("option_images")
    }


@router.delete("/questions/{question_id}")
async def delete_question(question_id: str, user: dict = Depends(get_admin_user)):
    """Delete a question"""
    result = await db.questions.delete_one({"question_id": question_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Question not found")
    return {"message": "Question deleted"}


# Simulators Admin
@router.post("/simulators", response_model=SimulatorResponse)
async def create_simulator(data: SimulatorCreate, user: dict = Depends(get_admin_user)):
    """Create a simulator"""
    simulator_id = AuthService.generate_id("sim_")
    now = datetime.now(timezone.utc).isoformat()
    area_config = UNAM_EXAM_CONFIG[data.area]
    
    await db.simulators.insert_one({
        "simulator_id": simulator_id,
        "name": data.name,
        "area": data.area,
        "description": data.description,
        "created_at": now
    })
    
    return SimulatorResponse(
        simulator_id=simulator_id,
        name=data.name,
        area=data.area,
        area_name=area_config["name"],
        area_color=area_config["color"],
        description=data.description,
        total_questions=TOTAL_QUESTIONS,
        duration_minutes=EXAM_DURATION_MINUTES,
        created_at=now
    )


@router.delete("/simulators/{simulator_id}")
async def delete_simulator(simulator_id: str, user: dict = Depends(get_admin_user)):
    """Delete a simulator"""
    result = await db.simulators.delete_one({"simulator_id": simulator_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Simulator not found")
    return {"message": "Simulator deleted"}


# Users Admin
@router.get("/users")
async def get_all_users(user: dict = Depends(get_admin_user)):
    """Get all users"""
    users = await db.users.find({}, {"_id": 0, "password": 0}).to_list(1000)
    result = []
    for u in users:
        attempts_count = await db.attempts.count_documents({"user_id": u["user_id"]})
        result.append({
            "user_id": u["user_id"],
            "email": u["email"],
            "name": u["name"],
            "role": u["role"],
            "picture": u.get("picture"),
            "created_at": u["created_at"],
            "attempts_count": attempts_count
        })
    result.sort(key=lambda x: x["created_at"], reverse=True)
    return result


@router.put("/users/{user_id}/role")
async def update_user_role(user_id: str, data: RoleUpdateRequest, admin: dict = Depends(get_admin_user)):
    """Update user role"""
    if user_id == admin["user_id"] and data.role == "student":
        raise HTTPException(status_code=400, detail="Cannot demote yourself")
    
    target = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.users.update_one({"user_id": user_id}, {"$set": {"role": data.role}})
    return {"message": f"Role updated to {data.role}"}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(get_admin_user)):
    """Delete a user"""
    if user_id == admin["user_id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    target = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.attempts.delete_many({"user_id": user_id})
    await db.user_sessions.delete_many({"user_id": user_id})
    await db.practice_sessions.delete_many({"user_id": user_id})
    await db.subscriptions.delete_many({"user_id": user_id})
    await db.users.delete_one({"user_id": user_id})
    
    return {"message": "User deleted"}


@router.post("/users/{user_id}/premium")
async def upgrade_to_premium(user_id: str, admin: dict = Depends(get_admin_user)):
    """Upgrade a user to premium (admin gift)"""
    target = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user already has active premium
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()
    
    # Find active subscription (compare as strings since that's how they're stored)
    existing = await db.subscriptions.find_one({
        "user_id": user_id,
        "status": "active"
    })
    
    # Check if subscription is still valid
    if existing:
        expires_at_str = existing["expires_at"]
        # Parse expiry date
        if isinstance(expires_at_str, str):
            if expires_at_str.endswith('Z'):
                expires_at_str = expires_at_str[:-1] + '+00:00'
            expires_at = datetime.fromisoformat(expires_at_str)
        else:
            expires_at = expires_at_str
        
        # If still valid, extend it
        if expires_at > now:
            new_expires = expires_at.replace(year=expires_at.year + 1)
            await db.subscriptions.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "expires_at": new_expires.isoformat(),
                    "updated_at": now_str
                }}
            )
            return {
                "message": "Premium extended by 1 year",
                "expires_at": new_expires.isoformat(),
                "extended": True
            }
    
    # Create new subscription (1 year from now)
    expires_at = now.replace(year=now.year + 1)
    subscription = {
        "user_id": user_id,
        "plan": "premium",
        "status": "active",
        "payment_method": "admin_gift",
        "amount": 0,
        "currency": "MXN",
        "created_at": now_str,
        "expires_at": expires_at.isoformat(),
        "stripe_subscription_id": None,
        "stripe_customer_id": None
    }
    
    await db.subscriptions.insert_one(subscription)
    
    return {
        "message": "User upgraded to premium",
        "expires_at": expires_at.isoformat(),
        "plan": "premium"
    }


@router.delete("/users/{user_id}/premium")
async def remove_premium(user_id: str, admin: dict = Depends(get_admin_user)):
    """Remove premium subscription from a user"""
    target = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    result = await db.subscriptions.update_many(
        {"user_id": user_id, "status": "active"},
        {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="No active subscription found")
    
    return {"message": "Premium subscription removed"}


@router.get("/users/{user_id}/subscription")
async def get_user_subscription(user_id: str, admin: dict = Depends(get_admin_user)):
    """Get any user's subscription status (admin only)"""
    from services.subscription_service import SubscriptionService
    
    target = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    subscription = await SubscriptionService.get_user_subscription(user_id)
    return subscription


# Reports Admin
@router.get("/reports")
async def get_reports(status: Optional[str] = None, user: dict = Depends(get_admin_user)):
    """Get all question reports"""
    query = {"status": status} if status else {}
    reports = await db.question_reports.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    result = []
    for r in reports:
        question = await db.questions.find_one({"question_id": r["question_id"]}, {"_id": 0, "text": 1, "subject_id": 1})
        reporter = await db.users.find_one({"user_id": r["user_id"]}, {"_id": 0, "name": 1, "email": 1})
        result.append({
            **r,
            "question_text": question["text"][:100] + "..." if question else "Pregunta eliminada",
            "reporter_name": reporter["name"] if reporter else "Usuario desconocido",
            "reporter_email": reporter["email"] if reporter else None
        })
    
    return result


@router.put("/reports/{report_id}")
async def update_report_status(report_id: str, status: str, user: dict = Depends(get_admin_user)):
    """Update report status"""
    if status not in ["pending", "reviewed", "resolved", "dismissed"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    result = await db.question_reports.update_one(
        {"report_id": report_id},
        {"$set": {"status": status, "reviewed_by": user["user_id"], "reviewed_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return {"message": "Reporte actualizado"}


# Rate Limiter Admin
@router.post("/rate-limit/cleanup")
async def cleanup_rate_limits(user: dict = Depends(get_admin_user)):
    """Cleanup old rate limit entries"""
    from utils.rate_limiter import rate_limiter
    removed = rate_limiter.cleanup_memory(max_age_seconds=3600)
    return {"message": f"Cleaned up {removed} expired entries", "removed_keys": removed}


@router.get("/rate-limit/status/{key}")
async def get_rate_limit_info(key: str, user: dict = Depends(get_admin_user)):
    """Get rate limit status for a key"""
    from utils.rate_limiter import rate_limiter
    status = await rate_limiter.get_status(key)
    return {"key": key, **status}


# Question Generation for Simulator Completion
@router.post("/generate-fill-questions/{area}")
async def generate_fill_questions(area: str, count: int = 50, user: dict = Depends(get_admin_user)):
    """
    Generate sample questions to fill simulators for a specific area.
    Areas:
    - area_1: matematicas, fisica
    - area_2: quimica, biologia
    - area_3: historia_universal, historia_mexico
    - area_4: filosofia
    """
    area_subjects = {
        "area_1": ["matematicas", "fisica"],
        "area_2": ["quimica", "biologia"],
        "area_3": ["historia_universal", "historia_mexico"],
        "area_4": ["filosofia"]
    }
    
    if area not in area_subjects:
        raise HTTPException(status_code=400, detail=f"Invalid area. Must be one of: {list(area_subjects.keys())}")
    
    subjects = area_subjects[area]
    generated = []
    
    for subject_slug in subjects:
        subject = await db.subjects.find_one({"slug": subject_slug}, {"_id": 0})
        if not subject:
            continue
        
        # Get existing count
        existing_count = await db.questions.count_documents({"subject_id": subject["subject_id"]})
        
        # Generate questions to reach desired count per subject
        questions_per_subject = count // len(subjects)
        to_generate = max(0, questions_per_subject - existing_count)
        
        if to_generate <= 0:
            generated.append({
                "subject": subject["name"],
                "existing": existing_count,
                "generated": 0,
                "message": "Already has enough questions"
            })
            continue
        
        # Sample questions by subject
        sample_questions = {
            "matematicas": [
                ("Álgebra", "Resuelve la ecuación: 2x + 5 = 15", ["x = 5", "x = 10", "x = 4", "x = 6"], 0, "Restar 5 de ambos lados: 2x = 10, luego dividir entre 2: x = 5"),
                ("Geometría", "¿Cuál es el área de un círculo con radio 3?", ["9π", "6π", "3π", "12π"], 0, "Área = πr² = π(3)² = 9π"),
                ("Trigonometría", "¿Cuál es el valor de sen(90°)?", ["1", "0", "-1", "0.5"], 0, "El seno de 90 grados es 1"),
                ("Cálculo", "¿Cuál es la derivada de x²?", ["2x", "x", "x²", "2"], 0, "La derivada de x² es 2x usando la regla de la potencia"),
                ("Estadística", "¿Cuál es la media de: 5, 10, 15?", ["10", "5", "15", "30"], 0, "(5+10+15)/3 = 30/3 = 10"),
            ],
            "fisica": [
                ("Mecánica", "¿Cuál es la fórmula de la segunda ley de Newton?", ["F = ma", "E = mc²", "P = mv", "V = IR"], 0, "Fuerza = masa × aceleración"),
                ("Cinemática", "¿Qué unidad mide la aceleración?", ["m/s²", "m/s", "kg·m/s", "N"], 0, "La aceleración se mide en metros por segundo al cuadrado"),
                ("Termodinámica", "¿Cuál es la temperatura de ebullición del agua?", ["100°C", "0°C", "50°C", "212°C"], 0, "El agua hierve a 100°C a nivel del mar"),
                ("Óptica", "¿Qué tipo de lente convergen los rayos de luz?", ["Convexa", "Cóncava", "Plana", "Cilíndrica"], 0, "Las lentes convexas convergen la luz"),
                ("Electricidad", "¿Cuál es la unidad de resistencia eléctrica?", ["Ohmio", "Voltio", "Amperio", "Watt"], 0, "El ohmio (Ω) es la unidad de resistencia"),
            ],
            "quimica": [
                ("Enlace Químico", "¿Qué tipo de enlace forma el NaCl?", ["Iónico", "Covalente", "Metálico", "Van der Waals"], 0, "El cloruro de sodio tiene enlace iónico"),
                ("Tabla Periódica", "¿Cuál es el símbolo del oro?", ["Au", "Ag", "Fe", "Cu"], 0, "Au viene del latín 'aurum'"),
                ("Reacciones", "¿Qué gas se libera en la fotosíntesis?", ["Oxígeno", "Dióxido de carbono", "Nitrógeno", "Hidrógeno"], 0, "Las plantas liberan oxígeno durante la fotosíntesis"),
                ("Ácidos y Bases", "¿Cuál es el pH del agua pura?", ["7", "1", "14", "0"], 0, "El agua pura tiene pH neutro de 7"),
                ("Estequiometría", "¿Cuántos átomos de oxígeno hay en CO₂?", ["2", "1", "3", "4"], 0, "El subíndice 2 indica dos átomos de oxígeno"),
            ],
            "biologia": [
                ("Célula", "¿Cuál es la función de la mitocondria?", ["Producir energía", "Síntesis de proteínas", "Almacenar agua", "Digestión celular"], 0, "Las mitocondrias producen ATP (energía)"),
                ("Genética", "¿Qué molécula lleva la información genética?", ["ADN", "ARN", "Proteína", "Lípido"], 0, "El ADN contiene la información hereditaria"),
                ("Fotosíntesis", "¿Dónde ocurre la fotosíntesis?", ["Cloroplastos", "Mitocondrias", "Núcleo", "Citoplasma"], 0, "La fotosíntesis ocurre en los cloroplastos"),
                ("Ecología", "¿Qué es un productor en un ecosistema?", ["Organismo que hace su propio alimento", "Animal que come plantas", "Animal que come carne", "Descomponedor"], 0, "Los productores (plantas) producen su propio alimento"),
                ("Evolución", "¿Quién propuso la teoría de la evolución?", ["Charles Darwin", "Isaac Newton", "Albert Einstein", "Gregor Mendel"], 0, "Darwin propuso la selección natural"),
            ],
            "historia_universal": [
                ("Edad Antigua", "¿Quién fue el primer emperador de Roma?", ["Augusto", "Julio César", "Nerón", "Constantino"], 0, "Augusto (Octavio) fue el primer emperador romano"),
                ("Revolución Francesa", "¿En qué año comenzó la Revolución Francesa?", ["1789", "1776", "1804", "1815"], 0, "La Revolución Francesa comenzó en 1789"),
                ("Segunda Guerra Mundial", "¿En qué año terminó la Segunda Guerra Mundial?", ["1945", "1939", "1941", "1950"], 0, "La WWII terminó en 1945"),
                ("Guerra Fría", "¿Qué era el Muro de Berlín?", ["Barrera que dividía Berlín", "Castillo medieval", "Monumento", "Muro de la Ciudad"], 0, "El Muro de Berlín dividió la ciudad durante la Guerra Fría"),
                ("Renacimiento", "¿Quién pintó la Mona Lisa?", ["Leonardo da Vinci", "Miguel Ángel", "Rafael", "Donatello"], 0, "Leonardo da Vinci pintó la Mona Lisa"),
            ],
            "historia_mexico": [
                ("Independencia", "¿En qué año comenzó la Independencia de México?", ["1810", "1821", "1910", "1812"], 0, "La Independencia comenzó en 1810 con el Grito de Dolores"),
                ("Revolución", "¿Quién inició la Revolución Mexicana?", ["Francisco I. Madero", "Porfirio Díaz", "Pancho Villa", "Emiliano Zapata"], 0, "Madero inició la Revolución en 1910"),
                ("Reforma", "¿Quién fue el presidente durante la Guerra de Reforma?", ["Benito Juárez", "Porfirio Díaz", "Maximiliano", "Santa Anna"], 0, "Benito Juárez fue presidente durante la Reforma"),
                ("Conquista", "¿Quién lideró la conquista de México?", ["Hernán Cortés", "Cristóbal Colón", "Moctezuma", "Cuauhtémoc"], 0, "Hernán Cortés conquistó México en 1521"),
                ("Virreinato", "¿Cuál fue la capital del Virreinato de Nueva España?", ["Ciudad de México", "Guadalajara", "Puebla", "Veracruz"], 0, "La capital fue Ciudad de México (México-Tenochtitlan)"),
            ],
            "filosofia": [
                ("Filosofía Antigua", "¿Quién dijo 'Conócete a ti mismo'?", ["Sócrates", "Platón", "Aristóteles", "Heráclito"], 0, "Este aforismo se atribuye a Sócrates"),
                ("Ética", "¿Quién escribió 'La República'?", ["Platón", "Aristóteles", "San Agustín", "Tomás de Aquino"], 0, "Platón escribió 'La República'"),
                ("Metafísica", "¿Qué filósofo dijo 'Pienso, luego existo'?", ["Descartes", "Kant", "Nietzsche", "Hegel"], 0, "René Descartes formuló el cogito"),
                ("Filosofía Moderna", "¿Quién propuso la teoría del imperativo categórico?", ["Kant", "Hume", "Locke", "Rousseau"], 0, "Kant propuso el imperativo categórico"),
                ("Existencialismo", "¿Quién escribió 'El extranjero'?", ["Albert Camus", "Jean-Paul Sartre", "Simone de Beauvoir", "Kierkegaard"], 0, "Albert Camus escribió 'El extranjero' (L'étranger)"),
            ]
        }
        
        samples = sample_questions.get(subject_slug, [])
        if not samples:
            continue
        
        created = 0
        for i in range(to_generate):
            sample = samples[i % len(samples)]
            topic, text, options, correct, explanation = sample
            
            # Create variation
            question_id = AuthService.generate_id("q_")
            question_doc = {
                "question_id": question_id,
                "subject_id": subject["subject_id"],
                "topic": topic,
                "text": f"{text} [{i+1}]",  # Add number to make unique
                "options": options,
                "correct_answer": correct,
                "explanation": explanation,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": user["user_id"]
            }
            
            try:
                await db.questions.insert_one(question_doc)
                created += 1
            except Exception as e:
                print(f"Error creating question: {e}")
        
        generated.append({
            "subject": subject["name"],
            "slug": subject_slug,
            "existing": existing_count,
            "generated": created,
            "new_total": existing_count + created
        })
    
    return {
        "area": area,
        "subjects_processed": subjects,
        "results": generated,
        "message": f"Generated questions for {area}. Check results for details."
    }
