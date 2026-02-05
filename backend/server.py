"""
IngresoUNAM API - Main Application Entry Point
Modular FastAPI application for UNAM exam preparation platform.
"""
import os
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv

from routes import create_api_router
from utils.config import CORS_ORIGINS

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')


# ============== SECURITY MIDDLEWARE ==============

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # Remove server header
        if "server" in response.headers:
            del response.headers["server"]
        return response


# ============== APPLICATION SETUP ==============

def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    
    # Determine if docs should be enabled
    enable_docs = os.environ.get("ENABLE_DOCS", "false").lower() == "true"
    
    app = FastAPI(
        title="IngresoUNAM API",
        version="1.0.0",
        docs_url="/api/docs" if enable_docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if enable_docs else None,
    )
    
    # Add security middleware
    app.add_middleware(SecurityHeadersMiddleware)
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_origins=CORS_ORIGINS,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Session-ID"],
    )
    
    # Include API router
    api_router = create_api_router()
    app.include_router(api_router)
    
    # Additional routes
    _register_additional_routes(app)
    
    # Serve frontend static files
    _serve_frontend(app)
    
    return app


def _register_additional_routes(app: FastAPI):
    """Register additional routes not in main router"""
    from datetime import datetime, timezone
    from fastapi import HTTPException, Request
    from utils.config import UNAM_EXAM_CONFIG, TOTAL_QUESTIONS, EXAM_DURATION_MINUTES, SUBJECT_ORDER, SUBJECT_NAMES
    from utils.database import db
    from utils.security import sanitize_string
    from services.auth_service import AuthService
    
    @app.get("/api/exam-config")
    async def get_exam_config():
        """Get exam configuration"""
        return {
            "areas": UNAM_EXAM_CONFIG,
            "total_questions": TOTAL_QUESTIONS,
            "duration_minutes": EXAM_DURATION_MINUTES,
            "subject_names": SUBJECT_NAMES,
            "subject_order": SUBJECT_ORDER
        }
    
    @app.post("/api/practice/start")
    async def start_practice(request: Request):
        """Start a practice session"""
        from routes.auth import get_current_user
        from services.subscription_service import SubscriptionService
        
        user = await get_current_user(request)
        data = await request.json()
        
        subject_id = data.get("subject_id")
        requested_count = min(max(data.get("question_count", 10), 5), 30)
        
        # Check practice access limits for free users
        access_check = await SubscriptionService.check_practice_access(user, requested_count)
        
        if not access_check["can_access"]:
            raise HTTPException(
                status_code=403,
                detail=access_check["limit_reason"]
            )
        
        # Use the allowed question count (may be limited for free users)
        question_count = access_check["max_questions"]
        
        subject = await db.subjects.find_one({"subject_id": subject_id}, {"_id": 0})
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")
        
        questions = await db.questions.aggregate([
            {"$match": {"subject_id": subject_id}},
            {"$sample": {"size": question_count}},
            {"$project": {"_id": 0}}
        ]).to_list(question_count)
        
        practice_id = AuthService.generate_id("practice_")
        now = datetime.now(timezone.utc).isoformat()
        
        await db.practice_sessions.insert_one({
            "practice_id": practice_id,
            "user_id": user["user_id"],
            "subject_id": subject_id,
            "subject_name": subject["name"],
            "question_ids": [q["question_id"] for q in questions],
            "answers": [],
            "started_at": now,
            "status": "in_progress"
        })
        
        response = {
            "practice_id": practice_id,
            "subject_name": subject["name"],
            "questions": [{
                "question_id": q["question_id"],
                "topic": q["topic"],
                "text": q["text"],
                "options": q["options"],
                "image_url": q.get("image_url"),
                "option_images": q.get("option_images")
            } for q in questions],
            "total_questions": len(questions),
            "is_premium": access_check["is_premium"]
        }
        
        # Add limit info for free users
        if not access_check["is_premium"]:
            response["limits"] = {
                "questions_remaining": access_check.get("questions_remaining", 0),
                "message": f"Preguntas restantes hoy: {access_check.get('questions_remaining', 0)}"
            }
        
        return response
    
    @app.post("/api/practice/{practice_id}/submit")
    async def submit_practice(practice_id: str, request: Request):
        """Submit practice session"""
        from routes.auth import get_current_user
        
        user = await get_current_user(request)
        data = await request.json()
        
        practice = await db.practice_sessions.find_one({
            "practice_id": practice_id,
            "user_id": user["user_id"]
        }, {"_id": 0})
        
        if not practice:
            raise HTTPException(status_code=404, detail="Practice session not found")
        if practice["status"] == "completed":
            raise HTTPException(status_code=400, detail="Practice already completed")
        
        answers = data.get("answers", [])
        results = []
        score = 0
        
        for answer in answers:
            question = await db.questions.find_one({"question_id": answer.get("question_id")}, {"_id": 0})
            if not question:
                continue
            
            is_correct = question["correct_answer"] == answer.get("selected_option")
            if is_correct:
                score += 1
            
            subject = await db.subjects.find_one({"subject_id": question["subject_id"]}, {"_id": 0})
            
            results.append({
                "question_id": answer.get("question_id"),
                "question_text": question["text"],
                "topic": question["topic"],
                "subject_name": subject["name"] if subject else "Unknown",
                "options": question["options"],
                "selected_option": answer.get("selected_option"),
                "correct_answer": question["correct_answer"],
                "is_correct": is_correct,
                "explanation": question["explanation"],
                "image_url": question.get("image_url"),
                "option_images": question.get("option_images")
            })
        
        now = datetime.now(timezone.utc).isoformat()
        await db.practice_sessions.update_one(
            {"practice_id": practice_id},
            {"$set": {"answers": results, "score": score, "finished_at": now, "status": "completed"}}
        )
        
        return {
            "practice_id": practice_id,
            "subject_name": practice["subject_name"],
            "score": score,
            "total": len(results),
            "percentage": round((score / len(results)) * 100, 1) if results else 0,
            "results": results
        }
    
    @app.get("/api/practice/{practice_id}/review")
    async def get_practice_review(practice_id: str, request: Request):
        """Get practice review"""
        from routes.auth import get_current_user
        
        user = await get_current_user(request)
        
        practice = await db.practice_sessions.find_one({
            "practice_id": practice_id,
            "user_id": user["user_id"],
            "status": "completed"
        }, {"_id": 0})
        
        if not practice:
            raise HTTPException(status_code=404, detail="Completed practice not found")
        
        return {
            "practice_id": practice_id,
            "subject_name": practice["subject_name"],
            "score": practice.get("score", 0),
            "total": len(practice.get("answers", [])),
            "results": practice.get("answers", []),
            "started_at": practice["started_at"],
            "finished_at": practice.get("finished_at")
        }
    
    @app.get("/api/user/limits")
    async def get_user_limits(request: Request):
        """Get user's remaining limits (simulators and practice)"""
        from routes.auth import get_current_user
        from services.subscription_service import SubscriptionService
        
        user = await get_current_user(request)
        limits = await SubscriptionService.get_remaining_limits(user["user_id"])
        
        return limits
    
    @app.post("/api/seed")
    async def seed_database(request: Request):
        """Seed database with initial data (protected)"""
        from routes.auth import get_current_user, get_admin_user
        
        client_ip = request.client.host if request.client else "unknown"
        
        # Allow from localhost or authenticated admin
        if client_ip not in ["127.0.0.1", "localhost", "::1"]:
            auth = request.headers.get("Authorization")
            if not auth or not auth.startswith("Bearer "):
                raise HTTPException(status_code=403, detail="Admin auth required")
            
            from services.auth_service import AuthService as AuthSvc
            payload = AuthSvc.decode_token(auth.split(" ")[1])
            if not payload:
                raise HTTPException(status_code=401, detail="Invalid token")
            
            user = await db.users.find_one({"user_id": payload["user_id"]}, {"_id": 0})
            if not user or user.get("role") != "admin":
                raise HTTPException(status_code=403, detail="Admin required")
        
        # Clear existing data
        await db.subjects.delete_many({})
        await db.questions.delete_many({})
        await db.simulators.delete_many({})
        
        # Insert subjects
        subjects_data = [
            {"subject_id": "subj_espanol", "name": "Espanol", "slug": "espanol"},
            {"subject_id": "subj_matematicas", "name": "Matematicas", "slug": "matematicas"},
            {"subject_id": "subj_fisica", "name": "Fisica", "slug": "fisica"},
            {"subject_id": "subj_literatura", "name": "Literatura", "slug": "literatura"},
            {"subject_id": "subj_geografia", "name": "Geografia", "slug": "geografia"},
            {"subject_id": "subj_biologia", "name": "Biologia", "slug": "biologia"},
            {"subject_id": "subj_quimica", "name": "Quimica", "slug": "quimica"},
            {"subject_id": "subj_historia_universal", "name": "Historia Universal", "slug": "historia_universal"},
            {"subject_id": "subj_historia_mexico", "name": "Historia de Mexico", "slug": "historia_mexico"},
            {"subject_id": "subj_filosofia", "name": "Filosofia", "slug": "filosofia"},
        ]
        await db.subjects.insert_many(subjects_data)
        
        # Sample questions
        templates = {
            "espanol": [("Gramatica", "Cual es el sujeto en 'El perro corre rapido'?", ["El perro", "corre", "rapido", "El"], 0, "El sujeto realiza la accion")],
            "matematicas": [("Algebra", "Si x + 5 = 12, cual es x?", ["5", "7", "12", "17"], 1, "x = 12 - 5 = 7")],
            "fisica": [("Mecanica", "La aceleracion de la gravedad es:", ["9.8 m/s²", "10 m/s²", "9.9 m/s²", "8.9 m/s²"], 0, "g ≈ 9.8 m/s²")],
            "literatura": [("Generos", "La tragedia pertenece al genero:", ["Dramatico", "Narrativo", "Lirico", "Epico"], 0, "El drama incluye tragedia")],
            "geografia": [("Fisica", "El rio mas largo es:", ["Nilo", "Amazonas", "Misisipi", "Yangtse"], 0, "El Nilo mide 6,650 km")],
            "biologia": [("Celula", "El nucleo contiene:", ["ADN", "Ribosomas", "Mitocondrias", "Cloroplastos"], 0, "El ADN esta en el nucleo")],
            "quimica": [("Elementos", "El simbolo del oro es:", ["Au", "Ag", "Fe", "Cu"], 0, "Au viene del latin aurum")],
            "historia_universal": [("Moderna", "La Revolucion Francesa fue en:", ["1789", "1776", "1810", "1917"], 0, "Inicio en 1789")],
            "historia_mexico": [("Independencia", "El Grito de Dolores fue en:", ["1810", "1821", "1910", "1857"], 0, "16 de septiembre de 1810")],
            "filosofia": [("Antigua", "Socrates fue maestro de:", ["Platon", "Aristoteles", "Tales", "Heraclito"], 0, "Platon fue discipulo de Socrates")],
        }
        
        questions = []
        for slug, tmpl_list in templates.items():
            subject_id = f"subj_{slug}"
            for i in range(30):
                t = tmpl_list[i % len(tmpl_list)]
                questions.append({
                    "question_id": AuthSvc.generate_id("q_"),
                    "subject_id": subject_id,
                    "topic": t[0],
                    "text": f"Pregunta {i+1}: {t[1]}" if i > 0 else t[1],
                    "options": t[2],
                    "correct_answer": t[3],
                    "explanation": t[4],
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
        await db.questions.insert_many(questions)
        
        # Create simulators
        simulators = [
            {"simulator_id": AuthService.generate_id("sim_"), "name": "Simulacro Area 1 - Ingenierias", "area": "area_1", "description": "Ciencias Fisico-Matematicas", "created_at": datetime.now(timezone.utc).isoformat()},
            {"simulator_id": AuthService.generate_id("sim_"), "name": "Simulacro Area 2 - Ciencias de la Salud", "area": "area_2", "description": "Ciencias Biologicas y Quimicas", "created_at": datetime.now(timezone.utc).isoformat()},
            {"simulator_id": AuthService.generate_id("sim_"), "name": "Simulacro Area 3 - Ciencias Sociales", "area": "area_3", "description": "Ciencias Sociales", "created_at": datetime.now(timezone.utc).isoformat()},
            {"simulator_id": AuthService.generate_id("sim_"), "name": "Simulacro Area 4 - Humanidades", "area": "area_4", "description": "Humanidades y Artes", "created_at": datetime.now(timezone.utc).isoformat()},
        ]
        await db.simulators.insert_many(simulators)
        
        # Create admin user if not exists
        if not await db.users.find_one({"email": "admin@ingresounam.com"}):
            await db.users.insert_one({
                "user_id": AuthService.generate_id("user_"),
                "email": "admin@ingresounam.com",
                "password": AuthService.hash_password("admin123"),
                "name": "Administrador",
                "role": "admin",
                "picture": None,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        
        return {
            "message": "Seeded",
            "subjects": len(subjects_data),
            "questions": len(questions),
            "simulators": len(simulators)
        }


# ============== LOGGING SETUP ==============

def setup_logging():
    """Configure application logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    # Don't log sensitive data
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


# ============== SHUTDOWN HANDLER ==============

async def shutdown_handler():
    """Cleanup on application shutdown"""
    from utils.database import client
    client.close()


def _serve_frontend(app: FastAPI):
    """Serve React frontend static files"""
    frontend_build_dir = ROOT_DIR.parent / "frontend" / "build"
    
    if frontend_build_dir.exists():
        # Mount static files
        app.mount("/static", StaticFiles(directory=str(frontend_build_dir / "static")), name="static")
        
        # Serve index.html for root path and all non-API routes
        @app.get("/", include_in_schema=False)
        async def serve_root():
            return FileResponse(str(frontend_build_dir / "index.html"))
        
        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            # Skip API routes
            if full_path.startswith("api/"):
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Not found")
            
            # Serve index.html for all other routes (SPA behavior)
            index_file = frontend_build_dir / "index.html"
            if index_file.exists():
                return FileResponse(str(index_file))
            
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Frontend not built")
    else:
        import logging
        logging.warning(f"Frontend build directory not found: {frontend_build_dir}")
        logging.warning("Run 'npm run build' in the frontend directory to build the frontend")


# ============== CREATE APP INSTANCE ==============

setup_logging()
app = create_app()

# Register startup event
@app.on_event("startup")
async def on_startup():
    """Initialize database indexes on startup"""
    from utils.database import setup_database_indexes
    await setup_database_indexes()
    print("[OK] Database indexes initialized")

# Register shutdown event
@app.on_event("shutdown")
async def on_shutdown():
    await shutdown_handler()
