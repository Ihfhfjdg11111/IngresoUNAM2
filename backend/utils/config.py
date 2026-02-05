"""
UNAM Exam Configuration Constants
"""
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

# ============== DATABASE CONFIGURATION ==============
MONGO_URL = os.environ.get('MONGO_URL')
if not MONGO_URL:
    raise ValueError("MONGO_URL environment variable is required")

DB_NAME = os.environ.get('DB_NAME')
if not DB_NAME:
    raise ValueError("DB_NAME environment variable is required")

# ============== JWT CONFIGURATION ==============
JWT_SECRET = os.environ.get('JWT_SECRET')
if not JWT_SECRET:
    import secrets
    JWT_SECRET = secrets.token_hex(32)
    import logging
    logging.warning("SECURITY WARNING: JWT_SECRET not set. Using generated secret.")

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24 * 7

# ============== REDIS CONFIGURATION (Optional) ==============
# Set REDIS_URL to enable distributed rate limiting across multiple servers
# Example: redis://localhost:6379/0 or redis://username:password@host:port/db
REDIS_URL = os.environ.get('REDIS_URL')

# ============== STRIPE CONFIGURATION ==============
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

# ============== GOOGLE OAUTH CONFIGURATION ==============
# Required for Google Sign-In
# Get credentials from: https://console.cloud.google.com/apis/credentials
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:3000/login')

# ============== CORS CONFIGURATION ==============
CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '').split(',')
if CORS_ORIGINS == ['']:
    CORS_ORIGINS = [
        "http://localhost:3000", "http://localhost:3001", "http://localhost:3002",
        "http://localhost:3003", "http://localhost:3004", "http://localhost:3005",
        "http://127.0.0.1:3000", "http://127.0.0.1:3001", "http://127.0.0.1:3002",
        "http://127.0.0.1:3003", "http://127.0.0.1:3004", "http://127.0.0.1:3005"
    ]

# ============== RATE LIMITING ==============
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX_REQUESTS = 100
RATE_LIMIT_MAX_LOGIN = 10

# ============== VALIDATION LIMITS ==============
MAX_NAME_LENGTH = 100
MAX_TEXT_LENGTH = 5000
MAX_TOPIC_LENGTH = 200
MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH = 128

# ============== EXAM CONFIGURATION ==============
TOTAL_QUESTIONS = 120
EXAM_DURATION_MINUTES = 180

# ============== FREE USER LIMITS ==============
# Configuración de límites para usuarios no premium (plan gratuito)

# Número de simulacros gratuitos por área (Área 1-4)
# Cada área tiene su propio contador independiente
FREE_SIMULATORS_PER_AREA = 3

# Número máximo de preguntas por práctica de materia (gratuitos)
# Usuarios premium pueden practicar hasta 30, gratuitos limitados a este número
FREE_PRACTICE_QUESTIONS_PER_DAY = 10

# Número máximo de prácticas por día (todas las materias combinadas)
FREE_PRACTICE_ATTEMPTS_PER_DAY = 5

# Número máximo de simulacros totales (todas las áreas combinadas) para gratuitos
# Este es un límite adicional de seguridad, más allá del por área
FREE_TOTAL_SIMULATORS_LIMIT = 12

# Características disponibles solo para premium
PREMIUM_FEATURES = {
    "unlimited_simulators": True,      # Simulacros ilimitados
    "unlimited_practice": True,        # Práctica ilimitada
    "detailed_analytics": True,        # Análisis detallado de resultados
    "progress_tracking": True,         # Seguimiento de progreso avanzado
    "download_results": True,          # Descargar resultados en PDF
    "priority_support": True,          # Soporte prioritario
}

# Subject order for exams
SUBJECT_ORDER = [
    "espanol", "fisica", "matematicas", "literatura", "geografia",
    "biologia", "quimica", "historia_universal", "historia_mexico", "filosofia"
]

# UNAM Exam Configuration by Area
UNAM_EXAM_CONFIG = {
    "area_1": {
        "name": "Ciencias Físico-Matemáticas e Ingenierías",
        "color": "#3B82F6",
        "subjects": {
            "espanol": 18, "matematicas": 26, "fisica": 16,
            "literatura": 10, "geografia": 10, "biologia": 10,
            "quimica": 10, "historia_universal": 10, "historia_mexico": 10
        }
    },
    "area_2": {
        "name": "Ciencias Biológicas, Químicas y de la Salud",
        "color": "#10B981",
        "subjects": {
            "espanol": 18, "matematicas": 24, "fisica": 12,
            "biologia": 13, "quimica": 13, "literatura": 10,
            "geografia": 10, "historia_universal": 10, "historia_mexico": 10
        }
    },
    "area_3": {
        "name": "Ciencias Sociales",
        "color": "#F59E0B",
        "subjects": {
            "espanol": 18, "matematicas": 24, "fisica": 10,
            "biologia": 10, "quimica": 10, "literatura": 10,
            "geografia": 10, "historia_universal": 14, "historia_mexico": 14
        }
    },
    "area_4": {
        "name": "Humanidades y Artes",
        "color": "#EF4444",
        "subjects": {
            "espanol": 18, "matematicas": 22, "fisica": 10,
            "biologia": 10, "quimica": 10, "literatura": 10,
            "geografia": 10, "historia_universal": 10, "historia_mexico": 10,
            "filosofia": 10
        }
    }
}

# Subscription Plans
SUBSCRIPTION_PLANS = {
    "monthly": {
        "name": "Mensual",
        "price": 10.00,
        "currency": "mxn",
        "duration_days": 30,
        "description": "Acceso ilimitado por 1 mes"
    },
    "quarterly": {
        "name": "Trimestral",
        "price": 25.00,
        "currency": "mxn",
        "duration_days": 90,
        "description": "Acceso ilimitado por 3 meses (¡Ahorra 17%!)"
    }
}

# Subject display names
SUBJECT_NAMES = {
    "matematicas": "Matemáticas", "fisica": "Física", "espanol": "Español",
    "literatura": "Literatura", "geografia": "Geografía", "biologia": "Biología",
    "quimica": "Química", "historia_universal": "Historia Universal",
    "historia_mexico": "Historia de México", "filosofia": "Filosofía"
}
