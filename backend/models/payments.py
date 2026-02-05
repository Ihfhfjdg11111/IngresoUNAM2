"""
Pydantic models for payments and subscriptions
"""
from typing import Optional, Dict
from pydantic import BaseModel, ConfigDict, field_validator
from utils.config import SUBSCRIPTION_PLANS, FREE_SIMULATORS_PER_AREA


class CheckoutRequest(BaseModel):
    plan_id: str
    origin_url: str

    @field_validator('plan_id')
    @classmethod
    def validate_plan(cls, v):
        if v not in SUBSCRIPTION_PLANS:
            raise ValueError('Invalid plan')
        return v


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    is_premium: bool
    plan_name: Optional[str] = None
    expires_at: Optional[str] = None
    simulators_used: Dict[str, int] = {}
    simulators_limit: int = FREE_SIMULATORS_PER_AREA
