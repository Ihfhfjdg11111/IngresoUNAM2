"""
Payment and subscription routes - Using direct Stripe SDK (no Emergent)
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request

from models import CheckoutRequest, SubscriptionResponse
from utils.database import db
from utils.config import SUBSCRIPTION_PLANS, FREE_SIMULATORS_PER_AREA, STRIPE_API_KEY, STRIPE_WEBHOOK_SECRET
from services.auth_service import AuthService
from services.subscription_service import SubscriptionService
from routes.auth import get_current_user

# Initialize Stripe only if key is available
stripe = None
if STRIPE_API_KEY:
    import stripe as stripe_lib
    stripe_lib.api_key = STRIPE_API_KEY
    stripe = stripe_lib

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.get("/subscription")
async def get_subscription_status(user: dict = Depends(get_current_user)):
    """Get user's subscription status"""
    subscription = await SubscriptionService.get_user_subscription(user["user_id"])
    usage = await SubscriptionService.get_user_simulator_usage(user["user_id"])
    
    return SubscriptionResponse(
        is_premium=subscription["is_premium"],
        plan_name=subscription.get("plan_name"),
        expires_at=subscription.get("expires_at"),
        simulators_used=usage,
        simulators_limit=FREE_SIMULATORS_PER_AREA
    )


@router.get("/plans")
async def get_subscription_plans():
    """Get available subscription plans"""
    return {
        "plans": [
            {
                "id": plan_id,
                "name": plan["name"],
                "price": plan["price"],
                "currency": plan["currency"],
                "duration_days": plan["duration_days"],
                "description": plan["description"]
            }
            for plan_id, plan in SUBSCRIPTION_PLANS.items()
        ],
        "free_limit": FREE_SIMULATORS_PER_AREA
    }


@router.post("/checkout")
async def create_checkout_session(data: CheckoutRequest, request: Request, user: dict = Depends(get_current_user)):
    """Create Stripe checkout session"""
    if not stripe:
        raise HTTPException(status_code=503, detail="Payment service not configured")
    
    plan = SUBSCRIPTION_PLANS.get(data.plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    try:
        # Create Stripe Checkout Session
        success_url = f"{data.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{data.origin_url}/payment/cancel"
        
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': plan['currency'],
                    'product_data': {
                        'name': plan['name'],
                        'description': plan['description'],
                    },
                    'unit_amount': int(plan['price'] * 100),  # Convert to cents
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'user_id': user["user_id"],
                'plan_id': data.plan_id,
                'plan_name': plan['name'],
                'duration_days': str(plan['duration_days'])
            },
            client_reference_id=user["user_id"],
        )
        
        # Create payment transaction record
        transaction_id = AuthService.generate_id("txn_")
        await db.payment_transactions.insert_one({
            "transaction_id": transaction_id,
            "session_id": session.id,
            "user_id": user["user_id"],
            "plan_id": data.plan_id,
            "amount": plan["price"],
            "currency": plan["currency"],
            "payment_status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        return {"url": session.url, "session_id": session.id}
        
    except Exception as e:
        print(f"Stripe error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


@router.get("/checkout/status/{session_id}")
async def get_checkout_status(session_id: str, user: dict = Depends(get_current_user)):
    """Check payment status and activate subscription"""
    if not stripe:
        raise HTTPException(status_code=503, detail="Payment service not configured")
    
    # Get transaction
    transaction = await db.payment_transactions.find_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    # If already processed
    if transaction["payment_status"] == "paid":
        return {"status": "complete", "payment_status": "paid", "already_processed": True}
    
    try:
        # Check status with Stripe
        session = stripe.checkout.Session.retrieve(session_id)
        
        # Update transaction status
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {
                "payment_status": session.payment_status,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # If paid, activate subscription
        if session.payment_status == "paid":
            plan = SUBSCRIPTION_PLANS.get(transaction["plan_id"])
            if plan:
                expires_at = datetime.now(timezone.utc) + timedelta(days=plan["duration_days"])
                subscription_id = AuthService.generate_id("sub_")
                
                # Deactivate existing subscriptions
                await db.subscriptions.update_many(
                    {"user_id": user["user_id"], "status": "active"},
                    {"$set": {"status": "replaced"}}
                )
                
                # Create new subscription
                await db.subscriptions.insert_one({
                    "subscription_id": subscription_id,
                    "user_id": user["user_id"],
                    "plan_id": transaction["plan_id"],
                    "plan_name": plan["name"],
                    "transaction_id": transaction["transaction_id"],
                    "status": "active",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "expires_at": expires_at.isoformat()
                })
        
        return {
            "status": session.status,
            "payment_status": session.payment_status,
            "amount_total": session.amount_total / 100 if session.amount_total else None,  # Convert from cents
            "currency": session.currency
        }
        
    except Exception as e:
        print(f"Stripe error: {e}")
        raise HTTPException(status_code=500, detail="Error checking payment status")


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    if not stripe or not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook not configured")
    
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    
    try:
        event = stripe.webhook.Event.construct_from(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        # Process payment
        transaction = await db.payment_transactions.find_one(
            {"session_id": session.id},
            {"_id": 0}
        )
        
        if transaction and transaction["payment_status"] != "paid":
            await db.payment_transactions.update_one(
                {"session_id": session.id},
                {"$set": {"payment_status": "paid", "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
            
            plan = SUBSCRIPTION_PLANS.get(transaction["plan_id"])
            if plan:
                expires_at = datetime.now(timezone.utc) + timedelta(days=plan["duration_days"])
                subscription_id = AuthService.generate_id("sub_")
                
                await db.subscriptions.update_many(
                    {"user_id": transaction["user_id"], "status": "active"},
                    {"$set": {"status": "replaced"}}
                )
                
                await db.subscriptions.insert_one({
                    "subscription_id": subscription_id,
                    "user_id": transaction["user_id"],
                    "plan_id": transaction["plan_id"],
                    "plan_name": plan["name"],
                    "transaction_id": transaction["transaction_id"],
                    "status": "active",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "expires_at": expires_at.isoformat()
                })
    
    return {"status": "success"}
