"""
Script para sembrar datos iniciales en MongoDB
"""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.database import db, client


def generate_id(prefix):
    """Generate unique ID"""
    import random
    import string
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
    return f"{prefix}{suffix}"


async def seed_database():
    """Seed database with initial data"""
    print("=" * 50)
    print("SEMIENDO DATOS INICIALES")
    print("=" * 50)
    
    try:
        # Clear existing data
        print("\nLimpiando colecciones existentes...")
        await db.subjects.delete_many({})
        await db.questions.delete_many({})
        await db.simulators.delete_many({})
        
        # Insert subjects
        print("Creando materias...")
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
        print("Creando preguntas de ejemplo...")
        templates = {
            "espanol": [("Gramatica", "Cual es el sujeto en 'El perro corre rapido'?", ["El perro", "corre", "rapido", "El"], 0, "El sujeto realiza la accion")],
            "matematicas": [("Algebra", "Si x + 5 = 12, cual es x?", ["5", "7", "12", "17"], 1, "x = 12 - 5 = 7")],
            "fisica": [("Mecanica", "La aceleracion de la gravedad es:", ["9.8 m/s", "10 m/s", "9.8 m/s", "8.9 m/s"], 0, "g = 9.8 m/s")],
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
                    "question_id": generate_id("q_"),
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
        print("Creando simuladores...")
        simulators = [
            {"simulator_id": generate_id("sim_"), "name": "Simulacro Area 1 - Ingenierias", "area": "area_1", "description": "Ciencias Fisico-Matematicas", "created_at": datetime.now(timezone.utc).isoformat()},
            {"simulator_id": generate_id("sim_"), "name": "Simulacro Area 2 - Ciencias de la Salud", "area": "area_2", "description": "Ciencias Biologicas y Quimicas", "created_at": datetime.now(timezone.utc).isoformat()},
            {"simulator_id": generate_id("sim_"), "name": "Simulacro Area 3 - Ciencias Sociales", "area": "area_3", "description": "Ciencias Sociales", "created_at": datetime.now(timezone.utc).isoformat()},
            {"simulator_id": generate_id("sim_"), "name": "Simulacro Area 4 - Humanidades", "area": "area_4", "description": "Humanidades y Artes", "created_at": datetime.now(timezone.utc).isoformat()},
        ]
        await db.simulators.insert_many(simulators)
        
        # Create admin user
        print("Creando usuario admin...")
        import bcrypt
        
        existing_admin = await db.users.find_one({"email": "admin@ingresounam.com"})
        if not existing_admin:
            password_hash = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
            await db.users.insert_one({
                "user_id": generate_id("user_"),
                "email": "admin@ingresounam.com",
                "password": password_hash,
                "name": "Administrador",
                "role": "admin",
                "picture": None,
                "subscription_status": "active",
                "subscription_expires_at": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            print("   Usuario admin creado: admin@ingresounam.com / admin123")
        else:
            print("   Usuario admin ya existe")
        
        # Summary
        print("\n" + "=" * 50)
        print("RESUMEN:")
        print("=" * 50)
        print(f"Materias: {len(subjects_data)}")
        print(f"Preguntas: {len(questions)}")
        print(f"Simuladores: {len(simulators)}")
        print(f"Usuarios admin: 1")
        print("\n[OK] Datos sembrados correctamente!")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        return False
    finally:
        client.close()


if __name__ == "__main__":
    success = asyncio.run(seed_database())
    sys.exit(0 if success else 1)
