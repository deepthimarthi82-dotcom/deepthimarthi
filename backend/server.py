from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import re
import json
import logging
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest

def extract_json(text: str) -> dict:
    """Extract JSON object from LLM response that may be wrapped in markdown fences."""
    if not text:
        raise ValueError("Empty response")
    # Strip markdown code fences if present
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    if fence_match:
        return json.loads(fence_match.group(1))
    # Find first { or [ and parse from there
    start = min((text.find(c) for c in "[{" if text.find(c) != -1), default=-1)
    if start == -1:
        raise ValueError(f"No JSON found in: {text[:200]}")
    # Find matching close bracket
    return json.loads(text[start:].strip())

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Config
JWT_SECRET = os.environ.get('JWT_SECRET', 'spark-dating-secret-key-2024')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 72

# Stripe Config
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', 'sk_test_emergent')

# LLM Config
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')

# Create the main app
app = FastAPI(title="Spark - Serious Dating App")
api_router = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

# ==================== WEBSOCKET MANAGER ====================

class ChatManager:
    """Manages active WebSocket connections per match for real-time chat."""
    def __init__(self):
        self.active: Dict[str, List[WebSocket]] = {}

    async def connect(self, match_id: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(match_id, []).append(ws)

    def disconnect(self, match_id: str, ws: WebSocket):
        if match_id in self.active:
            self.active[match_id] = [w for w in self.active[match_id] if w is not ws]
            if not self.active[match_id]:
                del self.active[match_id]

    async def broadcast(self, match_id: str, payload: dict):
        if match_id not in self.active:
            return
        dead = []
        for ws in self.active[match_id]:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(match_id, ws)

chat_manager = ChatManager()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== MODELS ====================

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserProfile(BaseModel):
    name: str
    age: int
    gender: str
    looking_for: str
    bio: str
    photos: List[str] = []
    location: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    languages: List[str] = []  # e.g. ["English", "Spanish", "Hindi"]
    job_title: Optional[str] = None
    company: Optional[str] = None
    education: Optional[str] = None
    height: Optional[str] = None
    intentions: Optional[str] = None
    dealbreakers: List[str] = []
    interests: List[str] = []
    prompts: List[Dict[str, str]] = []

class CompatibilityQuiz(BaseModel):
    communication_style: str
    conflict_resolution: str
    love_language: str
    life_goals: List[str]
    values: List[str]
    weekend_preference: str
    social_battery: str
    text_frequency: Optional[str] = None  # "constant", "daily", "couple-times-week", "minimal"

class SwipeAction(BaseModel):
    target_user_id: str
    action: str  # "like", "pass", "super_like"

class MessageCreate(BaseModel):
    match_id: str
    content: str
    message_type: str = "text"  # "text", "voice", "image"

class DateCheckin(BaseModel):
    match_id: str
    location: Optional[str] = None
    scheduled_time: datetime
    emergency_contact: Optional[str] = None

class CheckoutRequest(BaseModel):
    plan_id: str  # "premium_monthly", "premium_yearly", "vip_monthly", "vip_yearly"
    origin_url: str

class SafetySettings(BaseModel):
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_email: Optional[str] = None
    distance_unit: Optional[str] = "mi"  # "mi" or "km"
    language_filter_enabled: Optional[bool] = False

class ReportPayload(BaseModel):
    reason: str  # "harassment", "fake_profile", "spam", "inappropriate", "other"
    description: Optional[str] = None
    urgent: bool = False

class DatePlannerRequest(BaseModel):
    budget: str  # "$", "$$", "$$$"
    activity_type: str  # "food", "drinks", "outdoors", "culture", "active", "creative"
    city: Optional[str] = None

class SupportTicketCreate(BaseModel):
    name: str
    email: EmailStr
    issue_type: str  # "Bug Report", "Account Issue", "Safety Concern", "Billing", "Other"
    message: str
    urgent: bool = False

class BugReportCreate(BaseModel):
    description: str
    screenshot_data_url: Optional[str] = None  # base64 image
    page_url: Optional[str] = None
    browser: Optional[str] = None

# ==================== SUBSCRIPTION PLANS ====================

SUBSCRIPTION_PLANS = {
    "premium_monthly": {
        "name": "Premium Monthly",
        "price": 19.99,
        "features": [
            "Unlimited likes/swipes per day",
            "See exactly who liked you (unblurred)",
            "AI Date Planner",
            "Vibe Check detailed compatibility report",
            "Profile Boost — top of stack 30 min/week",
            "Global Passport — match in any city",
            "Read receipts on messages",
            "Voice messages in chat",
            "Undo last swipe",
            "Advanced filters (height, education, language, goal)",
            "See who viewed your profile"
        ]
    },
    "premium_yearly": {
        "name": "Premium Yearly",
        "price": 119.99,
        "features": [
            "Everything in Premium Monthly",
            "Save 50% vs monthly"
        ]
    },
    "vip_monthly": {
        "name": "VIP Monthly",
        "price": 39.99,
        "features": [
            "Everything in Premium",
            "3 Boosts per week",
            "Priority support",
            "VIP badge on your profile"
        ]
    },
    "vip_yearly": {
        "name": "VIP Yearly",
        "price": 239.99,
        "features": [
            "Everything in VIP Monthly",
            "Save 50% vs monthly"
        ]
    },
}

FREE_DAILY_SWIPES = 20
FREE_DAILY_SUPER_LIKES = 1
ADMIN_PREMIUM_EMAILS = {"deepthimarthi82@gmail.com", "vikaskesiraju@gmail.com"}

# ==================== UTILITIES ====================

import math
import httpx

def haversine_distance(lat1, lon1, lat2, lon2, unit="mi"):
    """Distance between two lat/lng points."""
    if None in (lat1, lon1, lat2, lon2):
        return None
    R = 3958.8 if unit == "mi" else 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dlon/2)**2
    return round(2 * R * math.asin(math.sqrt(a)), 1)

async def geocode_city(city: str, country: Optional[str] = None):
    """Geocode a city name to (lat, lng) using Nominatim. Returns (None, None) on failure."""
    q = f"{city}, {country}" if country else city
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": q, "format": "json", "limit": 1},
                headers={"User-Agent": "SparkMatch/1.0 (sparkmatch.dating)"}
            )
            data = r.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        logger.warning(f"Geocoding failed for '{q}': {e}")
    return None, None

# ==================== HELPERS ====================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

async def ensure_admin_premium(user: dict) -> dict:
    """If the user is an admin email, force-grant permanent premium (VIP)."""
    if user.get("email", "").lower() in ADMIN_PREMIUM_EMAILS:
        if user.get("subscription") != "vip" or not user.get("admin_premium"):
            far_future = (datetime.now(timezone.utc) + timedelta(days=36500)).isoformat()
            await db.users.update_one(
                {"id": user["id"]},
                {"$set": {
                    "subscription": "vip",
                    "subscription_expires": far_future,
                    "admin_premium": True,
                    "daily_swipes_remaining": 999999,
                    "daily_super_likes_remaining": 999999,
                }}
            )
            user["subscription"] = "vip"
            user["subscription_expires"] = far_future
            user["admin_premium"] = True
    return user

def create_token(user_id: str, email: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return await ensure_admin_premium(user)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ==================== AUTH ENDPOINTS ====================

@api_router.post("/auth/register")
async def register(user_data: UserCreate):
    email = user_data.email.lower()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = str(uuid.uuid4())
    is_admin = email in ADMIN_PREMIUM_EMAILS
    user = {
        "id": user_id,
        "email": email,
        "password": hash_password(user_data.password),
        "name": user_data.name,
        "profile_complete": False,
        "quiz_complete": False,
        "verified": False,
        "video_verified": False,
        "subscription": "vip" if is_admin else "free",
        "subscription_expires": (datetime.now(timezone.utc) + timedelta(days=36500)).isoformat() if is_admin else None,
        "admin_premium": is_admin,
        "daily_swipes_remaining": 999999 if is_admin else FREE_DAILY_SWIPES,
        "daily_super_likes_remaining": 999999 if is_admin else FREE_DAILY_SUPER_LIKES,
        "swipes_reset_date": datetime.now(timezone.utc).isoformat(),
        "boosts_remaining": 0,
        "last_active": datetime.now(timezone.utc).isoformat(),
        "response_rate": 100,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(user)
    
    token = create_token(user_id, email)
    return {"token": token, "user_id": user_id, "profile_complete": False}

@api_router.post("/auth/login")
async def login(credentials: UserLogin):
    email = credentials.email.lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not verify_password(credentials.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user = await ensure_admin_premium(user)
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_active": datetime.now(timezone.utc).isoformat()}})
    
    token = create_token(user["id"], user["email"])
    return {
        "token": token,
        "user_id": user["id"],
        "profile_complete": user.get("profile_complete", False),
        "quiz_complete": user.get("quiz_complete", False)
    }

@api_router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    user_copy = {k: v for k, v in user.items() if k != "password"}
    return user_copy

# ==================== PROFILE ENDPOINTS ====================

@api_router.put("/profile")
async def update_profile(profile: UserProfile, user: dict = Depends(get_current_user)):
    update_data = profile.model_dump()
    update_data["profile_complete"] = True
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    # Auto-geocode city if no coords provided
    if profile.location and (not profile.latitude or not profile.longitude):
        lat, lng = await geocode_city(profile.location, profile.country)
        if lat is not None:
            update_data["latitude"] = lat
            update_data["longitude"] = lng
    
    await db.users.update_one({"id": user["id"]}, {"$set": update_data})
    return {"message": "Profile updated", "profile_complete": True}

@api_router.put("/profile/quiz")
async def save_quiz(quiz: CompatibilityQuiz, user: dict = Depends(get_current_user)):
    quiz_data = quiz.model_dump()
    await db.users.update_one(
        {"id": user["id"]}, 
        {"$set": {"compatibility_quiz": quiz_data, "quiz_complete": True}}
    )
    return {"message": "Quiz saved", "quiz_complete": True}

@api_router.post("/profile/verify-video")
async def verify_video(user: dict = Depends(get_current_user)):
    # In production, this would verify against a live selfie
    # For MVP, we'll mark as verified
    await db.users.update_one({"id": user["id"]}, {"$set": {"video_verified": True}})
    return {"message": "Video verified", "verified": True}

@api_router.get("/profile/{user_id}")
async def get_profile(user_id: str, user: dict = Depends(get_current_user)):
    profile = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0, "email": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if there's a match to show full profile
    match = await db.matches.find_one({
        "$or": [
            {"user1_id": user["id"], "user2_id": user_id},
            {"user1_id": user_id, "user2_id": user["id"]}
        ],
        "status": "matched"
    })
    
    # Get compatibility score if exists
    compat = await db.compatibility_scores.find_one({
        "$or": [
            {"user1_id": user["id"], "user2_id": user_id},
            {"user1_id": user_id, "user2_id": user["id"]}
        ]
    }, {"_id": 0})
    
    profile["is_match"] = bool(match)
    profile["compatibility_score"] = compat.get("score") if compat else None
    profile["compatibility_insights"] = compat.get("insights") if compat else None
    
    return profile

# ==================== DISCOVERY & SWIPING ====================

@api_router.get("/discover")
async def discover_profiles(user: dict = Depends(get_current_user)):
    # Reset daily swipes if needed
    swipes_reset = datetime.fromisoformat(user.get("swipes_reset_date", datetime.now(timezone.utc).isoformat()))
    if datetime.now(timezone.utc).date() > swipes_reset.date():
        reset_swipes = FREE_DAILY_SWIPES if user.get("subscription") == "free" else 999999
        reset_super = FREE_DAILY_SUPER_LIKES if user.get("subscription") == "free" else (5 if "premium" in user.get("subscription", "") else 999999)
        await db.users.update_one({"id": user["id"]}, {"$set": {
            "daily_swipes_remaining": reset_swipes,
            "daily_super_likes_remaining": reset_super,
            "swipes_reset_date": datetime.now(timezone.utc).isoformat()
        }})
        user["daily_swipes_remaining"] = reset_swipes
        user["daily_super_likes_remaining"] = reset_super
    
    # Get users already swiped on
    swiped = await db.swipes.find({"swiper_id": user["id"]}).to_list(10000)
    swiped_ids = [s["swiped_id"] for s in swiped]
    swiped_ids.append(user["id"])  # Exclude self
    
    # Exclude blocked users (both directions)
    blocked = user.get("blocked_users", [])
    swiped_ids.extend(blocked)
    blocked_by_others = await db.blocks.find({"blocked_id": user["id"]}).to_list(1000)
    swiped_ids.extend([b["blocker_id"] for b in blocked_by_others])
    
    # Get user preferences
    looking_for = user.get("looking_for", "everyone")
    
    # Build query
    query = {
        "id": {"$nin": swiped_ids},
        "profile_complete": True
    }
    
    # Map looking_for to gender (women -> woman, men -> man)
    if looking_for == "women":
        query["gender"] = "woman"
    elif looking_for == "men":
        query["gender"] = "man"
    elif looking_for != "everyone":
        query["gender"] = looking_for
    
    # Optional language filter
    if user.get("language_filter_enabled") and user.get("languages"):
        query["languages"] = {"$in": user["languages"]}
    
    # Get potential matches
    profiles = await db.users.find(query, {"_id": 0, "password": 0, "email": 0}).limit(20).to_list(20)
    
    # Calculate compatibility + distance for each
    distance_unit = user.get("distance_unit", "mi")
    for profile in profiles:
        compat = await db.compatibility_scores.find_one({
            "$or": [
                {"user1_id": user["id"], "user2_id": profile["id"]},
                {"user1_id": profile["id"], "user2_id": user["id"]}
            ]
        }, {"_id": 0})
        profile["compatibility_score"] = compat.get("score") if compat else None
        profile["distance"] = haversine_distance(
            user.get("latitude"), user.get("longitude"),
            profile.get("latitude"), profile.get("longitude"),
            distance_unit
        )
        profile["distance_unit"] = distance_unit
    
    return {
        "profiles": profiles,
        "swipes_remaining": user.get("daily_swipes_remaining", FREE_DAILY_SWIPES),
        "super_likes_remaining": user.get("daily_super_likes_remaining", FREE_DAILY_SUPER_LIKES)
    }

@api_router.get("/discover/daily-picks")
async def get_daily_picks(user: dict = Depends(get_current_user)):
    """Get AI-curated daily picks (max 10)"""
    # Get users already swiped on
    swiped = await db.swipes.find({"swiper_id": user["id"]}).to_list(10000)
    swiped_ids = [s["swiped_id"] for s in swiped]
    swiped_ids.append(user["id"])
    
    looking_for = user.get("looking_for", "everyone")
    query = {"id": {"$nin": swiped_ids}, "profile_complete": True}
    if looking_for != "everyone":
        query["gender"] = looking_for
    
    # Get potential matches with high compatibility
    profiles = await db.users.find(query, {"_id": 0, "password": 0, "email": 0}).limit(50).to_list(50)
    
    # Sort by compatibility and verification
    scored_profiles = []
    for p in profiles:
        compat = await db.compatibility_scores.find_one({
            "$or": [
                {"user1_id": user["id"], "user2_id": p["id"]},
                {"user1_id": p["id"], "user2_id": user["id"]}
            ]
        }, {"_id": 0})
        score = compat.get("score", 50) if compat else 50
        # Boost verified users
        if p.get("video_verified"):
            score += 10
        scored_profiles.append((score, p))
    
    scored_profiles.sort(key=lambda x: x[0], reverse=True)
    daily_picks = [p for _, p in scored_profiles[:10]]
    
    for p in daily_picks:
        compat = await db.compatibility_scores.find_one({
            "$or": [
                {"user1_id": user["id"], "user2_id": p["id"]},
                {"user1_id": p["id"], "user2_id": user["id"]}
            ]
        }, {"_id": 0})
        p["compatibility_score"] = compat.get("score") if compat else None
    
    return {"daily_picks": daily_picks}

@api_router.post("/swipe")
async def swipe(action: SwipeAction, user: dict = Depends(get_current_user)):
    # Check swipe limits for free users
    if user.get("subscription") == "free":
        if action.action == "super_like" and user.get("daily_super_likes_remaining", 0) <= 0:
            raise HTTPException(status_code=403, detail="No super likes remaining. Upgrade to Premium!")
        if action.action in ["like", "pass"] and user.get("daily_swipes_remaining", 0) <= 0:
            raise HTTPException(status_code=403, detail="No swipes remaining today. Upgrade to Premium for unlimited!")
    
    # Record swipe
    swipe_record = {
        "id": str(uuid.uuid4()),
        "swiper_id": user["id"],
        "swiped_id": action.target_user_id,
        "action": action.action,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.swipes.insert_one(swipe_record)
    
    # Update remaining swipes
    if user.get("subscription") == "free":
        if action.action == "super_like":
            await db.users.update_one({"id": user["id"]}, {"$inc": {"daily_super_likes_remaining": -1}})
        else:
            await db.users.update_one({"id": user["id"]}, {"$inc": {"daily_swipes_remaining": -1}})
    
    # Check for match
    is_match = False
    match_data = None
    
    if action.action in ["like", "super_like"]:
        # Check if target has liked current user
        reverse_like = await db.swipes.find_one({
            "swiper_id": action.target_user_id,
            "swiped_id": user["id"],
            "action": {"$in": ["like", "super_like"]}
        })
        
        if reverse_like:
            is_match = True
            match_id = str(uuid.uuid4())
            # Set expiry to 7 days if no message
            expiry = datetime.now(timezone.utc) + timedelta(days=7)
            match_record = {
                "id": match_id,
                "user1_id": user["id"],
                "user2_id": action.target_user_id,
                "status": "matched",
                "matched_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": expiry.isoformat(),
                "has_messaged": False,
                "super_like": action.action == "super_like" or reverse_like.get("action") == "super_like"
            }
            await db.matches.insert_one(match_record)
            
            # Get matched user profile
            matched_user = await db.users.find_one({"id": action.target_user_id}, {"_id": 0, "password": 0, "email": 0})
            match_data = {"match_id": match_id, "user": matched_user}
    
    return {
        "success": True,
        "is_match": is_match,
        "match": match_data
    }

# ==================== MATCHES ====================

@api_router.get("/matches")
async def get_matches(user: dict = Depends(get_current_user)):
    matches = await db.matches.find({
        "$or": [{"user1_id": user["id"]}, {"user2_id": user["id"]}],
        "status": "matched"
    }, {"_id": 0}).to_list(100)
    
    result = []
    for match in matches:
        other_id = match["user2_id"] if match["user1_id"] == user["id"] else match["user1_id"]
        other_user = await db.users.find_one({"id": other_id}, {"_id": 0, "password": 0, "email": 0})
        
        # Get last message
        last_msg = await db.messages.find_one({"match_id": match["id"]}, {"_id": 0}, sort=[("created_at", -1)])
        
        # Check expiry
        expires_at = datetime.fromisoformat(match["expires_at"]) if match.get("expires_at") else None
        is_expired = expires_at and datetime.now(timezone.utc) > expires_at and not match.get("has_messaged")
        
        if not is_expired:
            result.append({
                "match_id": match["id"],
                "user": other_user,
                "matched_at": match["matched_at"],
                "expires_at": match.get("expires_at"),
                "has_messaged": match.get("has_messaged", False),
                "super_like": match.get("super_like", False),
                "last_message": last_msg
            })
    
    return {"matches": result}

@api_router.get("/likes-you")
async def get_likes(user: dict = Depends(get_current_user)):
    """See who liked you - Premium feature"""
    if user.get("subscription") == "free":
        # Return count only for free users
        likes = await db.swipes.find({
            "swiped_id": user["id"],
            "action": {"$in": ["like", "super_like"]}
        }).to_list(1000)
        
        # Filter out already matched
        matched = await db.matches.find({
            "$or": [{"user1_id": user["id"]}, {"user2_id": user["id"]}]
        }).to_list(1000)
        matched_ids = set()
        for m in matched:
            matched_ids.add(m["user1_id"])
            matched_ids.add(m["user2_id"])
        
        unmatched_likes = [l for l in likes if l["swiper_id"] not in matched_ids]
        
        return {"count": len(unmatched_likes), "is_premium_feature": True, "likes": []}
    
    # Premium users see who liked them
    likes = await db.swipes.find({
        "swiped_id": user["id"],
        "action": {"$in": ["like", "super_like"]}
    }, {"_id": 0}).to_list(100)
    
    matched = await db.matches.find({
        "$or": [{"user1_id": user["id"]}, {"user2_id": user["id"]}]
    }).to_list(1000)
    matched_ids = set()
    for m in matched:
        matched_ids.add(m["user1_id"])
        matched_ids.add(m["user2_id"])
    
    result = []
    for like in likes:
        if like["swiper_id"] not in matched_ids:
            liker = await db.users.find_one({"id": like["swiper_id"]}, {"_id": 0, "password": 0, "email": 0})
            if liker:
                result.append({
                    "user": liker,
                    "is_super_like": like["action"] == "super_like",
                    "liked_at": like["created_at"]
                })
    
    return {"count": len(result), "is_premium_feature": False, "likes": result}

@api_router.post("/unmatch/{match_id}")
async def unmatch(match_id: str, feedback: Optional[str] = None, user: dict = Depends(get_current_user)):
    match = await db.matches.find_one({"id": match_id})
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    if user["id"] not in [match["user1_id"], match["user2_id"]]:
        raise HTTPException(status_code=403, detail="Not your match")
    
    # Store anonymous feedback
    if feedback:
        other_id = match["user2_id"] if match["user1_id"] == user["id"] else match["user1_id"]
        await db.feedback.insert_one({
            "id": str(uuid.uuid4()),
            "about_user_id": other_id,
            "feedback": feedback,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    await db.matches.update_one({"id": match_id}, {"$set": {"status": "unmatched"}})
    return {"message": "Unmatched successfully"}

# ==================== MESSAGING ====================

@api_router.get("/messages/{match_id}")
async def get_messages(match_id: str, user: dict = Depends(get_current_user)):
    match = await db.matches.find_one({"id": match_id})
    if not match or user["id"] not in [match["user1_id"], match["user2_id"]]:
        raise HTTPException(status_code=403, detail="Not your match")
    
    messages = await db.messages.find({"match_id": match_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    
    # Mark as read
    await db.messages.update_many(
        {"match_id": match_id, "sender_id": {"$ne": user["id"]}, "read": False},
        {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"messages": messages}

@api_router.post("/messages")
async def send_message(msg: MessageCreate, user: dict = Depends(get_current_user)):
    match = await db.matches.find_one({"id": msg.match_id})
    if not match or user["id"] not in [match["user1_id"], match["user2_id"]]:
        raise HTTPException(status_code=403, detail="Not your match")
    
    message = {
        "id": str(uuid.uuid4()),
        "match_id": msg.match_id,
        "sender_id": user["id"],
        "content": msg.content,
        "message_type": msg.message_type,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.messages.insert_one(message)
    
    # Update match - prevent expiry
    await db.matches.update_one({"id": msg.match_id}, {"$set": {"has_messaged": True, "expires_at": None}})
    
    # Broadcast to WS subscribers (strip _id for JSON)
    broadcast_msg = {k: v for k, v in message.items() if k != "_id"}
    await chat_manager.broadcast(msg.match_id, {"type": "message", "message": broadcast_msg})
    
    return {"message": broadcast_msg}

@api_router.post("/messages/voice")
async def send_voice_message(
    match_id: str,
    duration: int,
    audio: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    """Upload a voice note. Premium-only feature."""
    if user.get("subscription", "free") == "free":
        raise HTTPException(status_code=402, detail={"premium_required": True, "feature": "Voice Messages", "message": "Upgrade to Premium to send voice messages."})
    match = await db.matches.find_one({"id": match_id})
    if not match or user["id"] not in [match["user1_id"], match["user2_id"]]:
        raise HTTPException(status_code=403, detail="Not your match")
    
    import base64
    data = await audio.read()
    if len(data) > 2 * 1024 * 1024:  # 2MB cap
        raise HTTPException(status_code=413, detail="Voice note too large (max 2MB)")
    
    mime = audio.content_type or "audio/webm"
    data_url = f"data:{mime};base64,{base64.b64encode(data).decode()}"
    
    message = {
        "id": str(uuid.uuid4()),
        "match_id": match_id,
        "sender_id": user["id"],
        "content": data_url,
        "message_type": "voice",
        "duration": duration,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.messages.insert_one(message)
    await db.matches.update_one({"id": match_id}, {"$set": {"has_messaged": True, "expires_at": None}})
    
    broadcast_msg = {k: v for k, v in message.items() if k != "_id"}
    await chat_manager.broadcast(match_id, {"type": "message", "message": broadcast_msg})
    
    return {"message": broadcast_msg}

@app.websocket("/api/ws/chat/{match_id}")
async def chat_websocket(websocket: WebSocket, match_id: str, token: str):
    """Real-time chat WebSocket. Auth via ?token=<jwt> query param."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload["user_id"]
    except Exception:
        await websocket.close(code=1008)
        return
    
    match = await db.matches.find_one({"id": match_id})
    if not match or user_id not in [match["user1_id"], match["user2_id"]]:
        await websocket.close(code=1008)
        return
    
    await chat_manager.connect(match_id, websocket)
    try:
        # Notify peer of join
        await chat_manager.broadcast(match_id, {"type": "presence", "user_id": user_id, "online": True})
        while True:
            data = await websocket.receive_json()
            # Typing indicator relay
            if data.get("type") == "typing":
                await chat_manager.broadcast(match_id, {"type": "typing", "user_id": user_id, "is_typing": bool(data.get("is_typing"))})
            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WS error: {e}")
    finally:
        chat_manager.disconnect(match_id, websocket)
        await chat_manager.broadcast(match_id, {"type": "presence", "user_id": user_id, "online": False})

# ==================== AI FEATURES ====================

@api_router.post("/ai/compatibility/{target_user_id}")
async def calculate_compatibility(target_user_id: str, user: dict = Depends(get_current_user)):
    """Calculate AI Vibe Check compatibility report between two users. Premium feature."""
    if user.get("subscription", "free") == "free":
        raise HTTPException(status_code=402, detail={"premium_required": True, "feature": "Vibe Check Report", "message": "Upgrade to Premium to see the detailed Vibe Compatibility report."})
    target = await db.users.find_one({"id": target_user_id}, {"_id": 0, "password": 0, "email": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already calculated recently
    existing = await db.compatibility_scores.find_one({
        "$or": [
            {"user1_id": user["id"], "user2_id": target_user_id},
            {"user1_id": target_user_id, "user2_id": user["id"]}
        ]
    })
    if existing:
        return {"score": existing["score"], "insights": existing["insights"]}
    
    # Build profiles for AI
    user_profile = f"""
    Name: {user.get('name')}
    Age: {user.get('age')}
    Bio: {user.get('bio')}
    Intentions: {user.get('intentions')}
    Interests: {', '.join(user.get('interests', []))}
    Dealbreakers: {', '.join(user.get('dealbreakers', []))}
    Quiz: {user.get('compatibility_quiz', {})}
    """
    
    target_profile = f"""
    Name: {target.get('name')}
    Age: {target.get('age')}
    Bio: {target.get('bio')}
    Intentions: {target.get('intentions')}
    Interests: {', '.join(target.get('interests', []))}
    Dealbreakers: {', '.join(target.get('dealbreakers', []))}
    Quiz: {target.get('compatibility_quiz', {})}
    """
    
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"compat-{user['id']}-{target_user_id}",
            system_message="""You are a dating compatibility expert. Analyze two profiles and provide:
            1. A compatibility score from 0-100
            2. 3 key compatibility insights (why they might work)
            3. 1 potential challenge to be aware of
            
            Respond ONLY with raw JSON, no markdown, no explanation: {"score": number, "insights": ["insight1", "insight2", "insight3"], "challenge": "string"}"""
        ).with_model("openai", "gpt-4o")
        
        response = await chat.send_message(UserMessage(
            text=f"Profile 1:\n{user_profile}\n\nProfile 2:\n{target_profile}"
        ))
        
        result = extract_json(response)
        
        # Store result
        await db.compatibility_scores.insert_one({
            "id": str(uuid.uuid4()),
            "user1_id": user["id"],
            "user2_id": target_user_id,
            "score": result["score"],
            "insights": result["insights"],
            "challenge": result.get("challenge"),
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        return result
    except Exception as e:
        logger.error(f"AI compatibility error: {e}")
        # Fallback to basic scoring
        score = 70
        return {"score": score, "insights": ["Both looking for serious relationships"], "challenge": "Get to know each other better!"}

@api_router.get("/ai/icebreakers/{match_id}")
async def get_icebreakers(match_id: str, user: dict = Depends(get_current_user)):
    """Get AI-generated conversation starters"""
    match = await db.matches.find_one({"id": match_id})
    if not match or user["id"] not in [match["user1_id"], match["user2_id"]]:
        raise HTTPException(status_code=403, detail="Not your match")
    
    other_id = match["user2_id"] if match["user1_id"] == user["id"] else match["user1_id"]
    other = await db.users.find_one({"id": other_id}, {"_id": 0, "password": 0, "email": 0})
    
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"ice-{match_id}",
            system_message="""Generate 5 unique, fun, and thoughtful conversation starters for a dating app match. 
            Make them specific to the person's profile. Be creative, not generic. Keep each under 120 chars.
            Respond ONLY with raw JSON, no markdown: {"icebreakers": ["question1", "question2", "question3", "question4", "question5"]}"""
        ).with_model("openai", "gpt-4o")
        
        profile_info = f"""
        Name: {other.get('name')}
        Bio: {other.get('bio')}
        Interests: {', '.join(other.get('interests', []))}
        Job: {other.get('job_title')} at {other.get('company', 'N/A')}
        Prompts: {other.get('prompts', [])}
        """
        
        response = await chat.send_message(UserMessage(text=f"Generate icebreakers for:\n{profile_info}"))
        
        result = extract_json(response)
        return result
    except Exception as e:
        logger.error(f"AI icebreakers error: {e}")
        return {"icebreakers": [
            f"Hey {other.get('name', 'there')}! What's the best thing that happened to you this week?",
            "If you could travel anywhere tomorrow, where would you go?",
            "What's something you're passionate about that most people don't know?",
            "Coffee or tea person? This is important! ☕",
            "What's on your bucket list?"
        ]}

@api_router.get("/ai/recap/{match_id}")
async def get_relationship_recap(match_id: str, force_refresh: bool = False, user: dict = Depends(get_current_user)):
    """Date Vault: AI-generated shareable recap of the conversation so far."""
    match = await db.matches.find_one({"id": match_id})
    if not match or user["id"] not in [match["user1_id"], match["user2_id"]]:
        raise HTTPException(status_code=403, detail="Not your match")

    msgs = await db.messages.find({"match_id": match_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    text_msgs = [m for m in msgs if m.get("message_type") != "voice"]
    if len(msgs) < 10:
        return {
            "unlocked": False,
            "messages_needed": 10 - len(msgs),
            "current_count": len(msgs),
            "message": f"Keep chatting! Date Vault unlocks at 10 messages ({10 - len(msgs)} to go)."
        }

    # Return cached recap unless force_refresh
    if not force_refresh:
        cached = await db.recaps.find_one(
            {"match_id": match_id},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
        if cached and cached.get("message_count_at_generation") == len(msgs):
            return {"unlocked": True, **cached}

    other_id = match["user2_id"] if match["user1_id"] == user["id"] else match["user1_id"]
    other = await db.users.find_one({"id": other_id}, {"_id": 0, "password": 0, "email": 0})

    transcript_lines = []
    for m in text_msgs[-100:]:  # cap context
        speaker = user.get("name", "You") if m["sender_id"] == user["id"] else other.get("name", "Match")
        transcript_lines.append(f"{speaker}: {m['content']}")
    transcript = "\n".join(transcript_lines)

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"recap-{match_id}-{len(msgs)}",
            system_message="""You are an expert relationship analyst writing a beautiful, shareable conversation recap. Analyze the chat transcript and produce:
- "vibe": one of "playful", "deep", "flirty", "intellectual", "warm", "adventurous"
- "headline": a punchy 6-10 word title for this relationship's story so far
- "sentiment_score": 0-100 (how positive/connected the conversation feels)
- "common_interests": array of 3-5 specific things they both seem to care about (extract from transcript, no generics)
- "memorable_moments": array of 2-3 short quotes or moments that stood out (one sentence each)
- "compatibility_signals": array of 2-3 reasons this could work long-term
- "next_step_suggestion": single concrete action they should take next (e.g. "Plan that hiking date you both joked about")
- "growth_area": one thing they could explore deeper

Respond ONLY with raw JSON, no markdown. Be warm, specific, never generic."""
        ).with_model("openai", "gpt-4o")

        response = await chat.send_message(UserMessage(
            text=f"Transcript between {user.get('name')} and {other.get('name')}:\n\n{transcript}"
        ))
        result = extract_json(response)
    except Exception as e:
        logger.error(f"Recap error: {e}")
        raise HTTPException(status_code=503, detail="Could not generate recap - try again in a moment")

    recap = {
        "id": str(uuid.uuid4()),
        "match_id": match_id,
        "generated_for_user_id": user["id"],
        "other_user_name": other.get("name"),
        "vibe": result.get("vibe"),
        "headline": result.get("headline"),
        "sentiment_score": result.get("sentiment_score"),
        "common_interests": result.get("common_interests", []),
        "memorable_moments": result.get("memorable_moments", []),
        "compatibility_signals": result.get("compatibility_signals", []),
        "next_step_suggestion": result.get("next_step_suggestion"),
        "growth_area": result.get("growth_area"),
        "message_count_at_generation": len(msgs),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.recaps.insert_one(dict(recap))
    return {"unlocked": True, **recap}

@api_router.get("/ai/date-ideas")
async def get_date_ideas(user: dict = Depends(get_current_user), location: Optional[str] = None):
    """Get AI-suggested date ideas based on location and interests"""
    user_location = location or user.get("location", "your city")
    interests = user.get("interests", [])
    
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"dates-{user['id']}",
            system_message="""Suggest 5 creative, memorable first date ideas. Mix classic and unique options.
            Consider the location and interests provided.
            Respond ONLY with raw JSON, no markdown: {"date_ideas": [{"title": "string", "description": "string", "vibe": "casual|romantic|adventurous|creative"}]}"""
        ).with_model("openai", "gpt-4o")
        
        response = await chat.send_message(UserMessage(
            text=f"Location: {user_location}\nInterests: {', '.join(interests) if interests else 'general'}"
        ))
        
        return extract_json(response)
    except Exception as e:
        logger.error(f"AI date ideas error: {e}")
        return {"date_ideas": [
            {"title": "Coffee & Walk", "description": "Grab coffee and explore a local park or neighborhood", "vibe": "casual"},
            {"title": "Sunset Picnic", "description": "Pack snacks and find a scenic spot for sunset", "vibe": "romantic"},
            {"title": "Mini Golf", "description": "Fun and competitive without being too serious", "vibe": "casual"},
            {"title": "Cooking Class", "description": "Learn something new together", "vibe": "creative"},
            {"title": "Live Music", "description": "Check out a local band or open mic night", "vibe": "adventurous"}
        ]}

# ==================== SAFETY FEATURES ====================

@api_router.post("/safety/checkin")
async def create_checkin(checkin: DateCheckin, user: dict = Depends(get_current_user)):
    """Create a date check-in for safety"""
    checkin_record = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "match_id": checkin.match_id,
        "location": checkin.location,
        "scheduled_time": checkin.scheduled_time.isoformat(),
        "emergency_contact": checkin.emergency_contact,
        "status": "scheduled",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.safety_checkins.insert_one(checkin_record)
    return {"checkin_id": checkin_record["id"], "message": "Check-in scheduled"}

@api_router.post("/safety/checkin/{checkin_id}/confirm")
async def confirm_safe(checkin_id: str, user: dict = Depends(get_current_user)):
    """Confirm you're safe after a date"""
    await db.safety_checkins.update_one(
        {"id": checkin_id, "user_id": user["id"]},
        {"$set": {"status": "confirmed_safe", "confirmed_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "Great! Glad you're safe!"}

@api_router.get("/safety/checkins")
async def get_checkins(user: dict = Depends(get_current_user)):
    """Get all check-ins"""
    checkins = await db.safety_checkins.find({"user_id": user["id"]}, {"_id": 0}).to_list(50)
    return {"checkins": checkins}

# ==================== PAYMENTS ====================

@api_router.get("/subscription/plans")
async def get_plans():
    """Get available subscription plans"""
    return {"plans": SUBSCRIPTION_PLANS}

@api_router.post("/subscription/checkout")
async def create_checkout(request: CheckoutRequest, http_request: Request, user: dict = Depends(get_current_user)):
    """Create Stripe checkout session"""
    if request.plan_id not in SUBSCRIPTION_PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    plan = SUBSCRIPTION_PLANS[request.plan_id]
    
    # Create checkout session
    host_url = request.origin_url
    webhook_url = f"{str(http_request.base_url).rstrip('/')}/api/webhook/stripe"
    
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    
    success_url = f"{host_url}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{host_url}/subscription"
    
    checkout_request = CheckoutSessionRequest(
        amount=float(plan["price"]),
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "user_id": user["id"],
            "plan_id": request.plan_id,
            "plan_name": plan["name"]
        }
    )
    
    session = await stripe_checkout.create_checkout_session(checkout_request)
    
    # Create payment transaction record
    await db.payment_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session.session_id,
        "user_id": user["id"],
        "plan_id": request.plan_id,
        "amount": plan["price"],
        "currency": "usd",
        "status": "pending",
        "payment_status": "initiated",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {"checkout_url": session.url, "session_id": session.session_id}

@api_router.get("/subscription/status/{session_id}")
async def check_payment_status(session_id: str, http_request: Request, user: dict = Depends(get_current_user)):
    """Check payment status and update subscription"""
    transaction = await db.payment_transactions.find_one({"session_id": session_id})
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    # If already processed, return status
    if transaction.get("payment_status") == "paid":
        return {"status": "paid", "plan": transaction.get("plan_id")}
    
    webhook_url = f"{str(http_request.base_url).rstrip('/')}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    
    status = await stripe_checkout.get_checkout_status(session_id)
    
    # Update transaction
    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {"$set": {
            "status": status.status,
            "payment_status": status.payment_status,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # If paid, update user subscription
    if status.payment_status == "paid" and transaction.get("payment_status") != "paid":
        plan_id = transaction["plan_id"]
        is_yearly = "yearly" in plan_id
        expires = datetime.now(timezone.utc) + timedelta(days=365 if is_yearly else 30)
        
        subscription_type = "vip" if "vip" in plan_id else "premium"
        
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {
                "subscription": subscription_type,
                "subscription_expires": expires.isoformat(),
                "daily_swipes_remaining": 999999,
                "daily_super_likes_remaining": 999999 if subscription_type == "vip" else 5
            }}
        )
    
    return {
        "status": status.status,
        "payment_status": status.payment_status,
        "plan": transaction.get("plan_id")
    }

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    body = await request.body()
    signature = request.headers.get("Stripe-Signature")
    
    webhook_url = f"{str(request.base_url).rstrip('/')}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    
    try:
        event = await stripe_checkout.handle_webhook(body, signature)
        logger.info(f"Stripe webhook: {event.event_type}")
        return {"received": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"received": True}

# ==================== BOOST ====================

@api_router.post("/boost")
async def use_boost(user: dict = Depends(get_current_user)):
    """Use a profile boost"""
    if user.get("boosts_remaining", 0) <= 0:
        if user.get("subscription") == "free":
            raise HTTPException(status_code=403, detail="Boosts are a premium feature")
        raise HTTPException(status_code=403, detail="No boosts remaining")
    
    boost_end = datetime.now(timezone.utc) + timedelta(minutes=30)
    
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"boosted_until": boost_end.isoformat()}, "$inc": {"boosts_remaining": -1}}
    )
    
    return {"message": "Boost activated!", "boosted_until": boost_end.isoformat()}

# ==================== SETTINGS ====================

@api_router.put("/settings/slow-dating")
async def toggle_slow_dating(enabled: bool, user: dict = Depends(get_current_user)):
    """Toggle slow dating mode - limits swipes to encourage quality"""
    await db.users.update_one({"id": user["id"]}, {"$set": {"slow_dating_mode": enabled}})
    return {"slow_dating_mode": enabled}

@api_router.get("/settings")
async def get_settings(user: dict = Depends(get_current_user)):
    return {
        "slow_dating_mode": user.get("slow_dating_mode", False),
        "subscription": user.get("subscription", "free"),
        "subscription_expires": user.get("subscription_expires"),
        "video_verified": user.get("video_verified", False)
    }

# ==================== SAFETY CENTER ====================

@api_router.get("/safety/me")
async def get_my_safety(user: dict = Depends(get_current_user)):
    return {
        "emergency_contact_name": user.get("emergency_contact_name"),
        "emergency_contact_phone": user.get("emergency_contact_phone"),
        "emergency_contact_email": user.get("emergency_contact_email"),
        "distance_unit": user.get("distance_unit", "mi"),
        "language_filter_enabled": user.get("language_filter_enabled", False),
        "blocked_count": len(user.get("blocked_users", []))
    }

@api_router.put("/safety/settings")
async def update_safety(settings: SafetySettings, user: dict = Depends(get_current_user)):
    update = {k: v for k, v in settings.model_dump().items() if v is not None}
    await db.users.update_one({"id": user["id"]}, {"$set": update})
    return {"message": "Safety settings updated", **update}

@api_router.post("/safety/block/{target_user_id}")
async def block_user(target_user_id: str, user: dict = Depends(get_current_user)):
    if target_user_id == user["id"]:
        raise HTTPException(status_code=400, detail="Cannot block yourself")
    await db.users.update_one({"id": user["id"]}, {"$addToSet": {"blocked_users": target_user_id}})
    await db.blocks.insert_one({
        "id": str(uuid.uuid4()),
        "blocker_id": user["id"],
        "blocked_id": target_user_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    # Auto-unmatch any match between them
    await db.matches.update_many(
        {"$or": [
            {"user1_id": user["id"], "user2_id": target_user_id},
            {"user1_id": target_user_id, "user2_id": user["id"]}
        ]},
        {"$set": {"status": "blocked"}}
    )
    return {"message": "User blocked"}

@api_router.post("/safety/unblock/{target_user_id}")
async def unblock_user(target_user_id: str, user: dict = Depends(get_current_user)):
    await db.users.update_one({"id": user["id"]}, {"$pull": {"blocked_users": target_user_id}})
    await db.blocks.delete_many({"blocker_id": user["id"], "blocked_id": target_user_id})
    return {"message": "User unblocked"}

@api_router.get("/safety/blocked")
async def list_blocked(user: dict = Depends(get_current_user)):
    blocked_ids = user.get("blocked_users", [])
    if not blocked_ids:
        return {"blocked": []}
    users = await db.users.find({"id": {"$in": blocked_ids}}, {"_id": 0, "password": 0, "email": 0}).to_list(100)
    return {"blocked": users}

@api_router.post("/safety/report/{target_user_id}")
async def report_user(target_user_id: str, payload: ReportPayload, user: dict = Depends(get_current_user)):
    report = {
        "id": str(uuid.uuid4()),
        "reporter_id": user["id"],
        "reported_id": target_user_id,
        "reason": payload.reason,
        "description": payload.description,
        "urgent": payload.urgent,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.reports.insert_one(report)
    return {"message": "Report submitted. Our safety team will review within 24 hours.", "report_id": report["id"]}

@api_router.post("/safety/panic")
async def panic_button(match_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Log a panic event and return emergency contact info for client-side actions (SMS/call)."""
    contact = {
        "name": user.get("emergency_contact_name"),
        "phone": user.get("emergency_contact_phone"),
        "email": user.get("emergency_contact_email"),
    }
    event = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "match_id": match_id,
        "contact": contact,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.panic_events.insert_one(event)
    if not any(contact.values()):
        return {"event_id": event["id"], "contact": None, "warning": "No emergency contact set. Please add one in the Safety Center."}
    return {"event_id": event["id"], "contact": contact}

# ==================== SUPPORT CENTER ====================

@api_router.post("/support/contact")
async def create_support_ticket(ticket: SupportTicketCreate, user: dict = Depends(get_current_user)):
    record = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "name": ticket.name,
        "email": ticket.email,
        "issue_type": ticket.issue_type,
        "message": ticket.message,
        "urgent": ticket.urgent,
        "status": "open",
        "deliver_to": "support@sparkmatch.dating",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.support_tickets.insert_one(record)
    return {"message": "Got it! Our team will email you back within 24h.", "ticket_id": record["id"]}

@api_router.post("/support/bug-report")
async def create_bug_report(report: BugReportCreate, user: dict = Depends(get_current_user)):
    if report.screenshot_data_url and len(report.screenshot_data_url) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Screenshot too large (max 5MB)")
    record = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "description": report.description,
        "screenshot_data_url": report.screenshot_data_url,
        "page_url": report.page_url,
        "browser": report.browser,
        "status": "open",
        "deliver_to": "support@sparkmatch.dating",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.bug_reports.insert_one(record)
    return {"message": "Bug report submitted. Thank you!", "report_id": record["id"]}

@api_router.get("/support/faq")
async def get_faq():
    """Static FAQ content."""
    return {"faqs": [
        {"q": "How does matching work?", "a": "Spark uses AI compatibility scoring based on your Vibe Check answers, interests, intentions, and conversation patterns. When two users like each other, it's a match!"},
        {"q": "How does Vibe Check work?", "a": "Before you start swiping, you answer a few quick questions about your communication style, conflict resolution, love language, and lifestyle. Our AI uses these to calculate a Vibe Compatibility Score (0-100%) for every potential match."},
        {"q": "How do I delete my account?", "a": "Go to Settings → Account → Delete Account. This permanently erases your profile, matches, messages, and all associated data within 30 days. This action cannot be undone."},
        {"q": "How do I report someone?", "a": "On any profile or in any chat, tap the shield icon. You can block, report (with optional details), or use the Panic Button to alert your emergency contact. Safety reports are reviewed within 24 hours."},
        {"q": "How do I cancel premium?", "a": "Go to Settings → Subscription → Manage. Your premium remains active until the end of your billing cycle. You will not be charged again."},
        {"q": "What's the 7-day countdown?", "a": "Every match has 7 days to agree to a real date. This keeps things moving and respects your time. You can request one 3-day extension if needed."},
        {"q": "Is Spark Match safe?", "a": "We offer video verification, date check-ins, block/report tools, a panic button linked to your emergency contact, and 24-hour safety team reviews. Always meet in public for the first date."}
    ]}

# ==================== AI DATE PLANNER ====================

@api_router.post("/ai/date-planner/{match_id}")
async def ai_date_planner(match_id: str, req: DatePlannerRequest, user: dict = Depends(get_current_user)):
    if user.get("subscription", "free") == "free":
        raise HTTPException(status_code=402, detail={"premium_required": True, "feature": "AI Date Planner", "message": "Upgrade to Premium to unlock the AI Date Planner."})
    match = await db.matches.find_one({"id": match_id})
    if not match or user["id"] not in [match["user1_id"], match["user2_id"]]:
        raise HTTPException(status_code=403, detail="Not your match")
    
    other_id = match["user2_id"] if match["user1_id"] == user["id"] else match["user1_id"]
    other = await db.users.find_one({"id": other_id}, {"_id": 0, "password": 0, "email": 0})
    
    city = req.city or user.get("location") or other.get("location") or "your city"
    your_interests = ", ".join(user.get("interests", [])) or "general"
    their_interests = ", ".join(other.get("interests", [])) or "general"
    
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"dateplanner-{match_id}-{datetime.now(timezone.utc).timestamp()}",
            system_message="""You are an expert date planner. Given two users' interests, a budget tier ($, $$, $$$), a preferred activity type, and a city, suggest 3 specific date ideas.
For each idea include:
- title (catchy)
- venue (REAL venue name in that city if possible, or generic if you don't know one)
- estimated_cost (number range in USD like "$30-50")
- duration (e.g. "2-3 hours")
- why_it_works (1-2 sentences referencing BOTH users' vibes)
- vibe (one of: romantic, fun, chill, adventurous, creative)

Respond ONLY with raw JSON, no markdown:
{"city": "string", "date_ideas": [{"title":"","venue":"","estimated_cost":"","duration":"","why_it_works":"","vibe":""}]}"""
        ).with_model("openai", "gpt-4o")
        
        response = await chat.send_message(UserMessage(
            text=f"City: {city}\nBudget: {req.budget}\nActivity type: {req.activity_type}\nUser A interests: {your_interests}\nUser B interests: {their_interests}"
        ))
        result = extract_json(response)
        return result
    except Exception as e:
        logger.error(f"Date planner error: {e}")
        raise HTTPException(status_code=503, detail="Couldn't generate date ideas right now — try again in a moment")

# ==================== DATE COUNTDOWN ====================

@api_router.post("/matches/{match_id}/extend")
async def extend_match(match_id: str, user: dict = Depends(get_current_user)):
    match = await db.matches.find_one({"id": match_id})
    if not match or user["id"] not in [match["user1_id"], match["user2_id"]]:
        raise HTTPException(status_code=403, detail="Not your match")
    if match.get("extended"):
        raise HTTPException(status_code=400, detail="This match has already been extended once")
    
    current_expiry = datetime.fromisoformat(match["expires_at"]) if match.get("expires_at") else datetime.now(timezone.utc)
    new_expiry = max(current_expiry, datetime.now(timezone.utc)) + timedelta(days=3)
    await db.matches.update_one({"id": match_id}, {"$set": {
        "expires_at": new_expiry.isoformat(),
        "extended": True,
        "extended_by": user["id"],
        "extended_at": datetime.now(timezone.utc).isoformat()
    }})
    return {"message": "Extended by 3 days!", "new_expiry": new_expiry.isoformat()}

@api_router.post("/matches/{match_id}/agree-date")
async def agree_to_date(match_id: str, user: dict = Depends(get_current_user)):
    """Either user can confirm they've agreed to meet — once both confirm, expiry is removed."""
    match = await db.matches.find_one({"id": match_id})
    if not match or user["id"] not in [match["user1_id"], match["user2_id"]]:
        raise HTTPException(status_code=403, detail="Not your match")
    
    field = "user1_agreed" if user["id"] == match["user1_id"] else "user2_agreed"
    update = {field: True, f"{field}_at": datetime.now(timezone.utc).isoformat()}
    await db.matches.update_one({"id": match_id}, {"$set": update})
    
    updated = await db.matches.find_one({"id": match_id})
    if updated.get("user1_agreed") and updated.get("user2_agreed"):
        await db.matches.update_one({"id": match_id}, {"$set": {"expires_at": None, "date_agreed": True}})
        return {"message": "Both of you agreed! Countdown stopped. Have an amazing date!", "both_agreed": True}
    
    return {"message": "Your agreement is recorded. Waiting for your match to confirm.", "both_agreed": False}

# ==================== ROOT ====================

@api_router.get("/")
async def root():
    return {"message": "Spark API - Find Your Forever Person"}

@api_router.get("/health")
async def health():
    return {"status": "healthy"}

# Include router and middleware
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
