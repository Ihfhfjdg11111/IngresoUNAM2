"""
Utils package - centralized exports
"""
import re
import html
import uuid
from datetime import datetime, timezone, timedelta

# Constants
MAX_NAME_LENGTH = 100
MAX_TEXT_LENGTH = 5000
MAX_TOPIC_LENGTH = 200
MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH = 128


def generate_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix"""
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def sanitize_string(text: str, max_length: int = MAX_TEXT_LENGTH) -> str:
    """Sanitize string input - escape HTML and limit length"""
    if not text:
        return ""
    # Remove null bytes and control characters
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Escape HTML entities
    text = html.escape(text.strip())
    return text[:max_length]


def validate_url(url: str) -> bool:
    """Validate URL format"""
    if not url:
        return True
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )
    return bool(url_pattern.match(url))


def validate_email(email: str) -> bool:
    """Basic email validation"""
    if not email:
        return False
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    return bool(email_pattern.match(email))


def validate_question_id(qid: str) -> bool:
    """Validate question ID format"""
    return bool(re.match(r'^q_[a-f0-9]{12}$', qid))
