"""
Subscription and payment service
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from utils.config import (
    FREE_SIMULATORS_PER_AREA, 
    FREE_PRACTICE_QUESTIONS_PER_DAY,
    FREE_PRACTICE_ATTEMPTS_PER_DAY,
    FREE_TOTAL_SIMULATORS_LIMIT
)
from utils.database import db


class SubscriptionService:
    """Service for subscription and payment operations"""
    
    @staticmethod
    async def get_user_subscription(user_id: str) -> dict:
        """Check if user has active subscription"""
        subscription = await db.subscriptions.find_one(
            {"user_id": user_id, "status": "active"},
            {"_id": 0}
        )
        
        if subscription:
            expires_at = subscription["expires_at"]
            # Handle various formats (string ISO or datetime object)
            if isinstance(expires_at, str):
                # Handle various ISO formats
                if expires_at.endswith('Z'):
                    expires_at = expires_at[:-1] + '+00:00'
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at > datetime.now(timezone.utc):
                return {
                    "is_premium": True,
                    "plan_name": subscription.get("plan_name"),
                    "expires_at": subscription["expires_at"]
                }
            else:
                # Subscription expired, update status
                await db.subscriptions.update_one(
                    {"subscription_id": subscription["subscription_id"]},
                    {"$set": {"status": "expired"}}
                )
        
        return {"is_premium": False, "plan_name": None, "expires_at": None}
    
    @staticmethod
    async def get_user_simulator_usage(user_id: str) -> Dict[str, int]:
        """Get count of simulators used per area"""
        pipeline = [
            {"$match": {"user_id": user_id, "status": "completed"}},
            {"$lookup": {
                "from": "simulators",
                "localField": "simulator_id",
                "foreignField": "simulator_id",
                "as": "simulator"
            }},
            {"$unwind": "$simulator"},
            {"$group": {"_id": "$simulator.area", "count": {"$sum": 1}}}
        ]
        
        result = await db.attempts.aggregate(pipeline).to_list(100)
        return {r["_id"]: r["count"] for r in result}
    
    @staticmethod
    async def get_total_simulator_usage(user_id: str) -> int:
        """Get total count of all simulators attempted"""
        return await db.attempts.count_documents({
            "user_id": user_id, 
            "status": "completed"
        })
    
    @staticmethod
    async def get_practice_usage_today(user_id: str) -> Dict[str, int]:
        """Get practice usage for today"""
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Count practice sessions today
        practice_count = await db.practice_sessions.count_documents({
            "user_id": user_id,
            "started_at": {"$gte": today_start.isoformat()}
        })
        
        # Count total questions practiced today
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "started_at": {"$gte": today_start.isoformat()}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_questions": {"$sum": {"$size": {"$ifNull": ["$answers", []]}}}
                }
            }
        ]
        
        result = await db.practice_sessions.aggregate(pipeline).to_list(1)
        total_questions = result[0]["total_questions"] if result else 0
        
        return {
            "practice_count": practice_count,
            "total_questions": total_questions
        }
    
    @staticmethod
    async def check_simulator_access(user: dict, simulator_area: str) -> bool:
        """Check if user can access a simulator (premium or within free limit)"""
        # Admin users always have access
        if user.get("role") == "admin":
            return True
        
        subscription = await SubscriptionService.get_user_subscription(user["user_id"])
        if subscription["is_premium"]:
            return True
        
        # Check free limit per area
        usage = await SubscriptionService.get_user_simulator_usage(user["user_id"])
        area_usage = usage.get(simulator_area, 0)
        
        if area_usage >= FREE_SIMULATORS_PER_AREA:
            return False
        
        # Also check total limit across all areas
        total_usage = await SubscriptionService.get_total_simulator_usage(user["user_id"])
        if total_usage >= FREE_TOTAL_SIMULATORS_LIMIT:
            return False
        
        return True
    
    @staticmethod
    async def check_practice_access(user: dict, requested_questions: int = 10) -> Dict[str, any]:
        """
        Check if user can access practice mode
        Returns dict with can_access (bool) and limit info
        """
        # Admin users always have access
        if user.get("role") == "admin":
            return {
                "can_access": True,
                "is_premium": True,
                "max_questions": 30,
                "limit_reason": None
            }
        
        subscription = await SubscriptionService.get_user_subscription(user["user_id"])
        if subscription["is_premium"]:
            return {
                "can_access": True,
                "is_premium": True,
                "max_questions": 30,
                "limit_reason": None
            }
        
        # Check free user limits
        usage = await SubscriptionService.get_practice_usage_today(user["user_id"])
        
        # Check daily practice attempts limit
        if usage["practice_count"] >= FREE_PRACTICE_ATTEMPTS_PER_DAY:
            return {
                "can_access": False,
                "is_premium": False,
                "max_questions": 0,
                "limit_reason": f"Has alcanzado el límite de {FREE_PRACTICE_ATTEMPTS_PER_DAY} prácticas por día. Suscríbete para práctica ilimitada."
            }
        
        # Check daily questions limit
        questions_remaining = FREE_PRACTICE_QUESTIONS_PER_DAY - usage["total_questions"]
        if questions_remaining <= 0:
            return {
                "can_access": False,
                "is_premium": False,
                "max_questions": 0,
                "limit_reason": f"Has alcanzado el límite de {FREE_PRACTICE_QUESTIONS_PER_DAY} preguntas de práctica por día. Suscríbete para práctica ilimitada."
            }
        
        # Allow but limit questions
        allowed_questions = min(requested_questions, questions_remaining)
        
        return {
            "can_access": True,
            "is_premium": False,
            "max_questions": allowed_questions,
            "questions_remaining": questions_remaining,
            "limit_reason": None
        }
    
    @staticmethod
    async def get_remaining_limits(user_id: str) -> Dict[str, any]:
        """Get remaining limits for a free user"""
        subscription = await SubscriptionService.get_user_subscription(user_id)
        
        if subscription["is_premium"]:
            return {
                "is_premium": True,
                "simulators": {"used": 0, "limit": "unlimited", "remaining": "unlimited"},
                "practice": {"used_today": 0, "limit": "unlimited", "remaining": "unlimited"}
            }
        
        # Get simulator usage
        area_usage = await SubscriptionService.get_user_simulator_usage(user_id)
        total_simulators = sum(area_usage.values())
        
        # Get practice usage
        practice_usage = await SubscriptionService.get_practice_usage_today(user_id)
        
        return {
            "is_premium": False,
            "simulators": {
                "per_area": {
                    "used_by_area": area_usage,
                    "limit_per_area": FREE_SIMULATORS_PER_AREA,
                    "total_used": total_simulators,
                    "total_limit": FREE_TOTAL_SIMULATORS_LIMIT
                },
                "remaining_per_area": {
                    area: max(0, FREE_SIMULATORS_PER_AREA - count)
                    for area, count in area_usage.items()
                },
                "total_remaining": max(0, FREE_TOTAL_SIMULATORS_LIMIT - total_simulators)
            },
            "practice": {
                "attempts_today": practice_usage["practice_count"],
                "attempts_limit": FREE_PRACTICE_ATTEMPTS_PER_DAY,
                "attempts_remaining": max(0, FREE_PRACTICE_ATTEMPTS_PER_DAY - practice_usage["practice_count"]),
                "questions_today": practice_usage["total_questions"],
                "questions_limit": FREE_PRACTICE_QUESTIONS_PER_DAY,
                "questions_remaining": max(0, FREE_PRACTICE_QUESTIONS_PER_DAY - practice_usage["total_questions"])
            }
        }
