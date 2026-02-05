"""
Security utilities for input sanitization and validation
"""
import re
import html
from utils.config import MAX_TEXT_LENGTH


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
        return False
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )
    return bool(url_pattern.match(url))


def validate_question_id(qid: str) -> bool:
    """Validate question ID format"""
    return bool(re.match(r'^q_[a-f0-9]{12}$', qid))
