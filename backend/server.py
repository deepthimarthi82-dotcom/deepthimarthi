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
JWT_EXPIRATION_HOURS = 24 * 30  # 30-day session expiry per security spec

# Stripe Config
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', 'sk_test_emergent')

# LLM Config
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')

# Create the main app
app = FastAPI(title="Spark - Serious Dating App")
api_router = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)
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
    date_of_birth: Optional[str] = None  # ISO date string YYYY-MM-DD

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
    education: Optional[str] = None  # high_school | associate | bachelor | master | doctorate | trade | other
    height: Optional[str] = None  # legacy free-form
    height_cm: Optional[int] = None  # numeric
    body_type: Optional[str] = None  # slim | athletic | average | curvy | plus | other
    drinking: Optional[str] = None  # never | rarely | socially | regularly | sober
    smoking: Optional[str] = None  # never | sometimes | regularly | trying_to_quit
    cannabis: Optional[str] = None  # never | sometimes | regularly
    religion: Optional[str] = None  # christian | catholic | muslim | jewish | hindu | buddhist | spiritual | atheist | agnostic | other
    politics: Optional[str] = None  # left | center_left | center | center_right | right | apolitical | other
    has_kids: Optional[str] = None  # no | yes_living_with | yes_not_living_with | prefer_not_say
    wants_kids: Optional[str] = None  # yes | no | maybe | open
    exercise: Optional[str] = None  # daily | weekly | sometimes | rarely | never
    pets: List[str] = []  # dog | cat | bird | reptile | fish | other | none
    intentions: Optional[str] = None
    dealbreakers: List[str] = []
    interests: List[str] = []
    prompts: List[Dict[str, str]] = []
    growth_goals: List[str] = []  # max 5
    icebreaker_answers: List[Dict[str, str]] = []  # [{question, answer}] max 3
    anti_ghosting_pledge: bool = False

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

FREE_DAILY_SWIPES = 30
FREE_DAILY_SUPER_LIKES = 1
WELLNESS_PROMPT_AT = 20  # show a gentle "slow down" prompt at this count
ADMIN_PREMIUM_EMAILS = {"deepthimarthi82@gmail.com", "vikaskesiraju@gmail.com"}

# ==================== UTILITIES ====================

import math
import httpx
import re as _re
import resend
import zipfile
import io
import secrets as _secrets
from cryptography.fernet import Fernet
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.responses import StreamingResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Encryption at rest (Fernet — AES-128-CBC + HMAC-SHA256, authenticated symmetric encryption)
_ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "")
_fernet = Fernet(_ENCRYPTION_KEY.encode()) if _ENCRYPTION_KEY else None

def encrypt_str(plain: Optional[str]) -> Optional[str]:
    if plain is None or _fernet is None:
        return plain
    return _fernet.encrypt(plain.encode()).decode()

def decrypt_str(cipher: Optional[str]) -> Optional[str]:
    if cipher is None or _fernet is None:
        return cipher
    try:
        return _fernet.decrypt(cipher.encode()).decode()
    except Exception:
        return cipher  # already plaintext (legacy data)

# Password strength check
_PASSWORD_RE = _re.compile(r"^(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?~`]).{8,}$")
def validate_password_strength(pw: str) -> Optional[str]:
    if not pw or len(pw) < 8:
        return "Password must be at least 8 characters"
    if not _re.search(r"\d", pw):
        return "Password must contain at least one number"
    if not _re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?~`]", pw):
        return "Password must contain at least one special character"
    return None

# Rate limiter (in-memory)
limiter = Limiter(key_func=get_remote_address, default_limits=["300/minute"])

@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request, exc):
    return JSONResponse(status_code=429, content={"detail": "Too many requests — slow down."})

# Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(self), camera=(self)"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.state.limiter = limiter
app.add_middleware(SecurityHeadersMiddleware)

# Resend

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
SUPPORT_INBOX = os.environ.get("SUPPORT_INBOX", "support@sparkmatch.dating")
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

async def send_email(to: str, subject: str, html: str, reply_to: Optional[str] = None) -> Optional[str]:
    """Send an email via Resend. Returns email id or None on failure. Never raises."""
    if not RESEND_API_KEY:
        logger.warning(f"Resend not configured, skipping email to {to}")
        return None
    params = {"from": SENDER_EMAIL, "to": [to], "subject": subject, "html": html}
    if reply_to:
        params["reply_to"] = reply_to
    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        return result.get("id") if isinstance(result, dict) else None
    except Exception as e:
        logger.warning(f"Email send failed to {to}: {e}")
        return None

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
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

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
        # Best-effort last_active bump (throttle to once per 60s to avoid write storms)
        try:
            now = datetime.now(timezone.utc)
            last_iso = user.get("last_active")
            should_update = True
            if last_iso:
                try:
                    last_dt = datetime.fromisoformat(last_iso.replace("Z", "+00:00"))
                    if last_dt.tzinfo is None: last_dt = last_dt.replace(tzinfo=timezone.utc)
                    if (now - last_dt).total_seconds() < 60:
                        should_update = False
                except Exception:
                    pass
            if should_update:
                now_iso = now.isoformat()
                asyncio.create_task(db.users.update_one({"id": user["id"]}, {"$set": {"last_active": now_iso}}))
                user["last_active"] = now_iso
        except Exception:
            pass
        return await ensure_admin_premium(user)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ==================== AUTH ENDPOINTS ====================

@api_router.post("/auth/register")
@limiter.limit("5/minute")
async def register(request: Request, user_data: UserCreate):
    email = user_data.email.lower().strip()
    
    # Password strength
    pw_err = validate_password_strength(user_data.password)
    if pw_err:
        raise HTTPException(status_code=400, detail=pw_err)
    
    # 18+ hard block via DOB (when provided)
    if user_data.date_of_birth:
        try:
            dob = datetime.fromisoformat(user_data.date_of_birth)
            age = (datetime.now(timezone.utc).replace(tzinfo=None) - dob.replace(tzinfo=None)).days // 365
            if age < 18:
                # Log the blocked attempt without storing PII
                await db.minor_block_attempts.insert_one({
                    "id": str(uuid.uuid4()),
                    "email_hash": hash_password(email)[:60],  # one-way
                    "ip": get_remote_address(request),
                    "age_estimate": age,
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                raise HTTPException(status_code=403, detail="Spark is for users 18 and older. You must be at least 18 to create an account.")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date of birth")
    
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
        "date_of_birth": user_data.date_of_birth,
        "profile_complete": False,
        "quiz_complete": False,
        "verified": False,
        "video_verified": False,
        "two_factor_enabled": False,
        "private_mode": False,
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
@limiter.limit("10/minute")
async def login(request: Request, credentials: UserLogin):
    email = credentials.email.lower().strip()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not verify_password(credentials.password, user["password"]):
        # Track failed login attempts for suspicious detection
        await db.failed_logins.insert_one({
            "email": email,
            "ip": get_remote_address(request),
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if user.get("suspended"):
        raise HTTPException(status_code=403, detail="Account suspended pending review. Contact support@sparkmatch.dating")
    
    # 2FA challenge if enabled
    if user.get("two_factor_enabled"):
        code = f"{_secrets.randbelow(900000) + 100000}"
        await db.two_factor_codes.insert_one({
            "user_id": user["id"],
            "code": code,
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            "used": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        html = f"""<h2>Your Spark verification code</h2>
<p style="font-size:32px;font-weight:bold;letter-spacing:6px;color:#FF2E63">{code}</p>
<p>Valid for 10 minutes. If you didn't request this, please change your password immediately.</p>"""
        asyncio.create_task(send_email(user["email"], "Your Spark login code", html))
        return {"two_factor_required": True, "user_id": user["id"], "message": "A 6-digit code was sent to your email"}
    
    user = await ensure_admin_premium(user)
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_active": datetime.now(timezone.utc).isoformat()}})
    
    token = create_token(user["id"], user["email"])
    return {
        "token": token,
        "user_id": user["id"],
        "profile_complete": user.get("profile_complete", False),
        "quiz_complete": user.get("quiz_complete", False)
    }

@api_router.post("/auth/2fa/verify")
@limiter.limit("10/minute")
async def verify_2fa(request: Request, payload: dict):
    user_id = payload.get("user_id")
    code = payload.get("code", "").strip()
    if not user_id or not code:
        raise HTTPException(status_code=400, detail="Missing user_id or code")
    record = await db.two_factor_codes.find_one(
        {"user_id": user_id, "code": code, "used": False},
        sort=[("created_at", -1)]
    )
    if not record or datetime.fromisoformat(record["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Invalid or expired code")
    await db.two_factor_codes.update_one({"_id": record["_id"]}, {"$set": {"used": True}})
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user = await ensure_admin_premium(user)
    token = create_token(user["id"], user["email"])
    return {
        "token": token,
        "user_id": user["id"],
        "profile_complete": user.get("profile_complete", False),
        "quiz_complete": user.get("quiz_complete", False)
    }

@api_router.post("/auth/2fa/toggle")
async def toggle_2fa(payload: dict, user: dict = Depends(get_current_user)):
    enabled = bool(payload.get("enabled"))
    await db.users.update_one({"id": user["id"]}, {"$set": {"two_factor_enabled": enabled}})
    return {"two_factor_enabled": enabled}

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
    profile["last_active_human"] = human_last_active(profile.get("last_active"))
    profile["is_online"] = is_online_now(profile.get("last_active"))
    
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
        "profile_complete": True,
        "$or": [
            {"wellness_paused_until": {"$exists": False}},
            {"wellness_paused_until": {"$lt": datetime.now(timezone.utc).isoformat()}}
        ]
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
    
    # Advanced filters (age range, height, education, etc.)
    _apply_advanced_filters_to_query(query, user)
    
    # Get potential matches
    profiles = await db.users.find(query, {"_id": 0, "password": 0, "email": 0}).limit(40).to_list(40)
    
    # Sort: boosted profiles first (active boost), then by last_active DESCENDING (most recent first)
    now_iso = datetime.now(timezone.utc).isoformat()
    def boost_active(p):
        bu = p.get("boost_active_until")
        return bool(bu and bu > now_iso)
    profiles.sort(key=lambda p: (0 if boost_active(p) else 1, -(len(p.get("last_active") or "")), p.get("last_active") or ""), reverse=False)
    # Re-sort the same-priority groups by last_active desc
    boosted = [p for p in profiles if boost_active(p)]
    others = [p for p in profiles if not boost_active(p)]
    boosted.sort(key=lambda p: p.get("last_active") or "", reverse=True)
    others.sort(key=lambda p: p.get("last_active") or "", reverse=True)
    profiles = (boosted + others)[:20]
    
    # Calculate compatibility + distance for each
    distance_unit = user.get("distance_unit", "mi")
    me_dna = user.get("personality_dna")
    for profile in profiles:
        compat = await db.compatibility_scores.find_one({
            "$or": [
                {"user1_id": user["id"], "user2_id": profile["id"]},
                {"user1_id": profile["id"], "user2_id": user["id"]}
            ]
        }, {"_id": 0})
        profile["compatibility_score"] = compat.get("score") if compat else None
        # Personality DNA score (40% weight contribution to overall match)
        them_dna = profile.get("personality_dna")
        if me_dna and them_dna:
            profile["personality_score"] = _personality_score(me_dna, them_dna)
            profile["personality_archetype"] = profile.get("personality_archetype")
        else:
            profile["personality_score"] = None
        profile["distance"] = haversine_distance(
            user.get("latitude"), user.get("longitude"),
            profile.get("latitude"), profile.get("longitude"),
            distance_unit
        )
        profile["distance_unit"] = distance_unit
        profile["is_boosted"] = boost_active(profile)
        profile["last_active_human"] = human_last_active(profile.get("last_active"))
        profile["is_online"] = is_online_now(profile.get("last_active"))
    
    # Apply distance filter (post-query because distance is computed)
    profiles = _apply_post_query_filters(profiles, user)
    
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
    asyncio.create_task(check_suspicious_swiping(user["id"]))
    
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
            # Fire push to BOTH users (best-effort, non-blocking)
            try:
                asyncio.create_task(push_on_new_match(user["id"], match_id, (matched_user or {}).get("name", "Someone")))
                asyncio.create_task(push_on_new_match(action.target_user_id, match_id, user.get("name", "Someone")))
            except Exception as e:
                logger.warning(f"Match push hook failed: {e}")
    
    return {
        "success": True,
        "is_match": is_match,
        "match": match_data
    }

@api_router.post("/swipe/undo")
async def undo_swipe(user: dict = Depends(get_current_user)):
    """Undo your most recent swipe. Premium-only."""
    if user.get("subscription", "free") == "free":
        raise HTTPException(status_code=402, detail={"premium_required": True, "feature": "Undo Swipe", "message": "Upgrade to Premium to undo your last swipe."})
    last = await db.swipes.find_one(
        {"swiper_id": user["id"]},
        {"_id": 0},
        sort=[("created_at", -1)]
    )
    if not last:
        raise HTTPException(status_code=404, detail="No swipes to undo")
    # If this swipe created a match, remove the match
    await db.matches.delete_many({
        "$or": [
            {"user1_id": user["id"], "user2_id": last["swiped_id"]},
            {"user1_id": last["swiped_id"], "user2_id": user["id"]}
        ],
        "matched_at": {"$gte": last["created_at"]}
    })
    await db.swipes.delete_one({"id": last["id"]})
    return {"undone": last["swiped_id"], "action": last["action"]}

# ==================== PROFILE BOOST ====================

@api_router.post("/me/boost")
async def boost_profile(user: dict = Depends(get_current_user)):
    """Activate Profile Boost — top of stack for 30 minutes. Premium-only, 1/week (3/week for VIP)."""
    if user.get("subscription", "free") == "free":
        raise HTTPException(status_code=402, detail={"premium_required": True, "feature": "Profile Boost", "message": "Upgrade to Premium to boost your profile."})
    
    is_vip = user.get("subscription") == "vip"
    boost_limit = 3 if is_vip else 1
    
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()
    used_this_week = await db.boost_events.count_documents({
        "user_id": user["id"],
        "created_at": {"$gte": week_ago}
    })
    if used_this_week >= boost_limit:
        raise HTTPException(status_code=429, detail=f"You've used all {boost_limit} boosts this week. Resets in 7 days.")
    
    boost_until = (now + timedelta(minutes=30)).isoformat()
    await db.users.update_one({"id": user["id"]}, {"$set": {"boost_active_until": boost_until}})
    await db.boost_events.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "active_until": boost_until,
        "created_at": now.isoformat()
    })
    return {"boost_active_until": boost_until, "boosts_remaining_this_week": boost_limit - used_this_week - 1}

@api_router.get("/me/boost/status")
async def boost_status(user: dict = Depends(get_current_user)):
    """Check if user has an active boost + how many remain this week."""
    is_premium = user.get("subscription", "free") != "free"
    is_vip = user.get("subscription") == "vip"
    boost_limit = 3 if is_vip else (1 if is_premium else 0)
    
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    used_this_week = await db.boost_events.count_documents({"user_id": user["id"], "created_at": {"$gte": week_ago}})
    
    active_until = user.get("boost_active_until")
    is_active = False
    if active_until:
        try:
            is_active = datetime.fromisoformat(active_until) > datetime.now(timezone.utc)
        except Exception:
            is_active = False
    
    return {
        "is_active": is_active,
        "active_until": active_until if is_active else None,
        "boosts_remaining_this_week": max(0, boost_limit - used_this_week),
        "weekly_limit": boost_limit
    }

# ==================== PROFILE VIEWERS ====================

@api_router.post("/profile/view/{target_user_id}")
async def record_profile_view(target_user_id: str, user: dict = Depends(get_current_user)):
    """Record that current user viewed target's profile. Idempotent within 1 hour."""
    if target_user_id == user["id"]:
        return {"recorded": False}
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    existing = await db.profile_views.find_one({
        "viewer_id": user["id"],
        "viewed_id": target_user_id,
        "created_at": {"$gte": one_hour_ago}
    })
    if existing:
        return {"recorded": False, "deduped": True}
    await db.profile_views.insert_one({
        "id": str(uuid.uuid4()),
        "viewer_id": user["id"],
        "viewed_id": target_user_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    return {"recorded": True}

@api_router.get("/me/viewers")
async def list_profile_viewers(user: dict = Depends(get_current_user)):
    """See users who viewed your profile in the last 30 days. Premium-only."""
    if user.get("subscription", "free") == "free":
        raise HTTPException(status_code=402, detail={"premium_required": True, "feature": "Profile Viewers", "message": "Upgrade to Premium to see who viewed your profile."})
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    pipeline = [
        {"$match": {"viewed_id": user["id"], "created_at": {"$gte": thirty_days_ago}}},
        {"$sort": {"created_at": -1}},
        {"$group": {"_id": "$viewer_id", "last_viewed_at": {"$first": "$created_at"}, "view_count": {"$sum": 1}}},
        {"$limit": 100}
    ]
    rows = await db.profile_views.aggregate(pipeline).to_list(100)
    viewer_ids = [r["_id"] for r in rows]
    # Exclude viewers with private mode enabled
    viewers = await db.users.find(
        {"id": {"$in": viewer_ids}, "$or": [{"private_mode": {"$exists": False}}, {"private_mode": False}]},
        {"_id": 0, "password": 0, "email": 0}
    ).to_list(100)
    by_id = {v["id"]: v for v in viewers}
    result = []
    for r in rows:
        if r["_id"] in by_id:
            result.append({**by_id[r["_id"]], "last_viewed_at": r["last_viewed_at"], "view_count": r["view_count"]})
    return {"viewers": result, "total": len(result)}

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
        if other_user:
            other_user["last_active_human"] = human_last_active(other_user.get("last_active"))
            other_user["is_online"] = is_online_now(other_user.get("last_active"))
        
        # Get last message
        last_msg = await db.messages.find_one({"match_id": match["id"]}, {"_id": 0}, sort=[("created_at", -1)])
        if last_msg and last_msg.get("encrypted") and last_msg.get("message_type") != "voice":
            last_msg["content"] = decrypt_str(last_msg.get("content"))
        
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
        
        unmatched_likes = [lk for lk in likes if lk["swiper_id"] not in matched_ids]
        
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
    # Decrypt text messages
    for m in messages:
        if m.get("encrypted") and m.get("message_type") != "voice":
            m["content"] = decrypt_str(m.get("content"))
    
    # Mark as read
    await db.messages.update_many(
        {"match_id": match_id, "sender_id": {"$ne": user["id"]}, "read": False},
        {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"messages": messages}

@api_router.post("/messages")
@limiter.limit("60/minute")
async def send_message(request: Request, msg: MessageCreate, user: dict = Depends(get_current_user)):
    match = await db.matches.find_one({"id": msg.match_id})
    if not match or user["id"] not in [match["user1_id"], match["user2_id"]]:
        raise HTTPException(status_code=403, detail="Not your match")
    
    message = {
        "id": str(uuid.uuid4()),
        "match_id": msg.match_id,
        "sender_id": user["id"],
        "content": encrypt_str(msg.content),
        "message_type": msg.message_type,
        "read": False,
        "encrypted": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.messages.insert_one(message)
    
    # Update match - prevent expiry
    await db.matches.update_one({"id": msg.match_id}, {"$set": {"has_messaged": True, "expires_at": None}})
    
    # Broadcast decrypted to live WS listeners
    broadcast_msg = {k: v for k, v in message.items() if k != "_id"}
    broadcast_msg["content"] = msg.content  # send plaintext over secured TLS WS
    await chat_manager.broadcast(msg.match_id, {"type": "message", "message": broadcast_msg})
    
    # Suspicious activity check (50+ messages in last hour)
    asyncio.create_task(check_suspicious_messaging(user["id"]))
    
    # Push the recipient (best-effort)
    receiver_id = match["user2_id"] if match["user1_id"] == user["id"] else match["user1_id"]
    try:
        asyncio.create_task(push_on_new_message(receiver_id, user.get("name", "Spark"), msg.match_id, msg.content))
    except Exception as e:
        logger.warning(f"Message push hook failed: {e}")
    
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
    # Decrypt for analysis
    for m in msgs:
        if m.get("encrypted") and m.get("message_type") != "voice":
            m["content"] = decrypt_str(m.get("content"))
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
    # Delete all matches AND their messages between them (silent + permanent)
    match_ids = []
    async for m in db.matches.find({"$or": [
        {"user1_id": user["id"], "user2_id": target_user_id},
        {"user1_id": target_user_id, "user2_id": user["id"]}
    ]}):
        match_ids.append(m["id"])
    if match_ids:
        await db.messages.delete_many({"match_id": {"$in": match_ids}})
        await db.matches.delete_many({"id": {"$in": match_ids}})
    # Delete any swipes either direction
    await db.swipes.delete_many({"$or": [
        {"swiper_id": user["id"], "swiped_id": target_user_id},
        {"swiper_id": target_user_id, "swiped_id": user["id"]}
    ]})
    return {"message": "User blocked. They are completely hidden from you."}

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
    asyncio.create_task(check_report_threshold(target_user_id))
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
        "deliver_to": SUPPORT_INBOX,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.support_tickets.insert_one(record)
    # Fire-and-forget emails (non-blocking)
    urgency = "🚨 URGENT — " if ticket.urgent else ""
    inbox_html = f"""<h2>{urgency}New Support Ticket — {ticket.issue_type}</h2>
<p><b>From:</b> {ticket.name} &lt;{ticket.email}&gt;</p>
<p><b>Ticket ID:</b> {record['id']}</p>
<p><b>Message:</b></p><blockquote>{ticket.message}</blockquote>"""
    asyncio.create_task(send_email(SUPPORT_INBOX, f"{urgency}[{ticket.issue_type}] {ticket.name}", inbox_html, reply_to=ticket.email))
    ack_html = f"""<h2>We got your message!</h2>
<p>Hi {ticket.name},</p>
<p>Thanks for reaching out to Spark Match. Our team will review your <b>{ticket.issue_type}</b> ticket and reply within 24 hours.</p>
<p><b>Ticket ID:</b> {record['id']}</p>
<p>Love,<br/>The Spark Team</p>"""
    asyncio.create_task(send_email(ticket.email, f"We got your message — ticket #{record['id'][:8]}", ack_html))
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
        "deliver_to": SUPPORT_INBOX,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.bug_reports.insert_one(record)
    inbox_html = f"""<h2>🐛 New Bug Report</h2>
<p><b>User:</b> {user.get('email')}</p>
<p><b>Page:</b> {report.page_url or 'unknown'}</p>
<p><b>Browser:</b> {report.browser or 'unknown'}</p>
<p><b>Description:</b></p><blockquote>{report.description}</blockquote>
{'<p><b>Screenshot attached inline in DB record.</b></p>' if report.screenshot_data_url else ''}"""
    asyncio.create_task(send_email(SUPPORT_INBOX, f"[Bug] {report.description[:60]}", inbox_html, reply_to=user.get("email")))
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

# ==================== SUSPICIOUS ACTIVITY DETECTION ====================

async def _flag_account(user_id: str, reason: str, severity: str = "medium"):
    """Flag and (optionally) auto-suspend an account; alert admin."""
    flag = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "reason": reason,
        "severity": severity,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.security_flags.insert_one(flag)
    if severity in ("high", "critical"):
        await db.users.update_one({"id": user_id}, {"$set": {"suspended": True, "suspended_reason": reason}})
    # Notify admin
    u = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    html = f"""<h2>🚨 Suspicious activity flagged</h2>
<p><b>User:</b> {u.get('email') if u else user_id}</p>
<p><b>Reason:</b> {reason}</p>
<p><b>Severity:</b> {severity}</p>
<p><b>Status:</b> {'AUTO-SUSPENDED' if severity in ('high','critical') else 'flagged for review'}</p>"""
    asyncio.create_task(send_email("deepthimarthi82@gmail.com", f"[Spark Security] {severity.upper()} — {reason}", html))

async def check_suspicious_messaging(user_id: str):
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    count = await db.messages.count_documents({"sender_id": user_id, "created_at": {"$gte": one_hour_ago}})
    if count > 50:
        # Avoid duplicate flag
        recent = await db.security_flags.find_one({"user_id": user_id, "reason": "messaging_spam", "created_at": {"$gte": one_hour_ago}})
        if not recent:
            await _flag_account(user_id, "messaging_spam", "high")

async def check_suspicious_swiping(user_id: str):
    today = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    likes = await db.swipes.count_documents({"swiper_id": user_id, "action": {"$in": ["like", "super_like"]}, "created_at": {"$gte": today}})
    passes = await db.swipes.count_documents({"swiper_id": user_id, "action": "pass", "created_at": {"$gte": today}})
    total = likes + passes
    if total >= 30 and passes == 0:
        await _flag_account(user_id, "swipe_bot_behavior", "high")

async def check_report_threshold(user_id: str):
    count = await db.reports.count_documents({"reported_id": user_id})
    if count >= 3:
        await _flag_account(user_id, "multiple_reports", "high")

# ==================== ACCOUNT DELETION + DATA EXPORT ====================

@api_router.post("/account/delete/request")
async def request_account_deletion(user: dict = Depends(get_current_user)):
    """Step 1: schedules deletion in 30 days + sends confirmation email."""
    deletion_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    confirm_token = _secrets.token_urlsafe(32)
    await db.users.update_one({"id": user["id"]}, {"$set": {
        "pending_deletion_at": deletion_at,
        "deletion_confirm_token": confirm_token
    }})
    html = f"""<h2>Account Deletion Confirmation</h2>
<p>Hi {user.get('name')},</p>
<p>We received a request to delete your Spark account. Your account and all data will be permanently deleted on <b>{deletion_at[:10]}</b>.</p>
<p>If this was you and you want to delete <b>immediately</b>, click the button in the app to confirm with this token: <code>{confirm_token[:12]}...</code></p>
<p>If you change your mind, log in to Spark anytime in the next 30 days and we'll cancel the deletion.</p>
<p>Spark complies with the California Consumer Privacy Act (CCPA). Your right to deletion is honored.</p>"""
    asyncio.create_task(send_email(user["email"], "Confirm your Spark account deletion", html))
    return {"message": "Confirmation email sent. Your account is scheduled for permanent deletion in 30 days.", "pending_deletion_at": deletion_at}

@api_router.post("/account/delete/cancel")
async def cancel_account_deletion(user: dict = Depends(get_current_user)):
    await db.users.update_one({"id": user["id"]}, {"$unset": {"pending_deletion_at": "", "deletion_confirm_token": ""}})
    return {"message": "Account deletion cancelled. Welcome back!"}

@api_router.post("/account/delete/confirm")
async def confirm_immediate_deletion(payload: dict, user: dict = Depends(get_current_user)):
    """Immediate deletion (user re-confirms in-app)."""
    confirmed = payload.get("confirm") == "DELETE FOREVER"
    if not confirmed:
        raise HTTPException(status_code=400, detail="Type 'DELETE FOREVER' to confirm")
    uid = user["id"]
    # Cascade delete
    await db.users.delete_one({"id": uid})
    await db.swipes.delete_many({"$or": [{"swiper_id": uid}, {"swiped_id": uid}]})
    await db.matches.delete_many({"$or": [{"user1_id": uid}, {"user2_id": uid}]})
    await db.messages.delete_many({"sender_id": uid})
    await db.profile_views.delete_many({"$or": [{"viewer_id": uid}, {"viewed_id": uid}]})
    await db.compatibility_scores.delete_many({"$or": [{"user1_id": uid}, {"user2_id": uid}]})
    await db.recaps.delete_many({"generated_for_user_id": uid})
    await db.reports.delete_many({"reporter_id": uid})
    await db.blocks.delete_many({"$or": [{"blocker_id": uid}, {"blocked_id": uid}]})
    await db.profile_views.delete_many({"$or": [{"viewer_id": uid}, {"viewed_id": uid}]})
    await db.boost_events.delete_many({"user_id": uid})
    await db.two_factor_codes.delete_many({"user_id": uid})
    await db.account_deletions.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": uid,
        "completed_at": datetime.now(timezone.utc).isoformat()
    })
    return {"message": "Your account and all associated data have been permanently deleted. Goodbye!"}

@api_router.get("/account/export")
async def export_user_data(user: dict = Depends(get_current_user)):
    """CCPA-compliant data export as a ZIP file."""
    uid = user["id"]
    
    # Gather all data
    user_profile = await db.users.find_one({"id": uid}, {"_id": 0, "password": 0})
    swipes = await db.swipes.find({"swiper_id": uid}, {"_id": 0}).to_list(10000)
    matches = await db.matches.find({"$or": [{"user1_id": uid}, {"user2_id": uid}]}, {"_id": 0}).to_list(10000)
    messages_raw = await db.messages.find({"sender_id": uid}, {"_id": 0}).to_list(10000)
    for m in messages_raw:
        if m.get("encrypted") and m.get("message_type") != "voice":
            m["content"] = decrypt_str(m.get("content"))
    reports_sent = await db.reports.find({"reporter_id": uid}, {"_id": 0}).to_list(1000)
    viewers = await db.profile_views.find({"$or": [{"viewer_id": uid}, {"viewed_id": uid}]}, {"_id": 0}).to_list(1000)
    
    # Build ZIP in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", f"Spark Match — Personal Data Export\nGenerated for: {user.get('email')}\nDate: {datetime.now(timezone.utc).isoformat()}\n\nThis archive contains all data Spark has on your account, per CCPA and GDPR.")
        z.writestr("profile.json", json.dumps(user_profile, indent=2, default=str))
        z.writestr("swipes.json", json.dumps(swipes, indent=2, default=str))
        z.writestr("matches.json", json.dumps(matches, indent=2, default=str))
        z.writestr("messages_sent.json", json.dumps(messages_raw, indent=2, default=str))
        z.writestr("reports_filed.json", json.dumps(reports_sent, indent=2, default=str))
        z.writestr("profile_view_activity.json", json.dumps(viewers, indent=2, default=str))
    buf.seek(0)
    
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="spark-data-{uid[:8]}.zip"'}
    )

# ==================== PRIVATE MODE ====================

@api_router.put("/me/private-mode")
async def toggle_private_mode(payload: dict, user: dict = Depends(get_current_user)):
    if user.get("subscription", "free") == "free":
        raise HTTPException(status_code=402, detail={"premium_required": True, "feature": "Private Mode", "message": "Upgrade to Premium for invisible browsing."})
    enabled = bool(payload.get("enabled"))
    await db.users.update_one({"id": user["id"]}, {"$set": {"private_mode": enabled}})
    return {"private_mode": enabled}

# ==================== ADMIN SECURITY ====================

@api_router.get("/admin/security/flags")
async def list_security_flags(user: dict = Depends(get_current_user)):
    if user.get("email", "").lower() not in ADMIN_PREMIUM_EMAILS:
        raise HTTPException(status_code=403, detail="Admin only")
    flags = await db.security_flags.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    user_ids = list({f["user_id"] for f in flags})
    users = await db.users.find({"id": {"$in": user_ids}}, {"_id": 0, "password": 0}).to_list(200)
    by_id = {u["id"]: u for u in users}
    for f in flags:
        u = by_id.get(f["user_id"], {})
        f["user_email"] = u.get("email")
        f["user_name"] = u.get("name")
        f["suspended"] = u.get("suspended", False)
    return {"flags": flags, "total": len(flags)}

@api_router.post("/admin/security/resolve/{flag_id}")
async def resolve_flag(flag_id: str, payload: dict, user: dict = Depends(get_current_user)):
    if user.get("email", "").lower() not in ADMIN_PREMIUM_EMAILS:
        raise HTTPException(status_code=403, detail="Admin only")
    action = payload.get("action")  # "dismiss" | "suspend" | "unsuspend"
    if action not in ("dismiss", "suspend", "unsuspend"):
        raise HTTPException(status_code=400, detail="Invalid action")
    flag = await db.security_flags.find_one({"id": flag_id})
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    if action == "suspend":
        await db.users.update_one({"id": flag["user_id"]}, {"$set": {"suspended": True, "suspended_reason": flag["reason"]}})
    elif action == "unsuspend":
        await db.users.update_one({"id": flag["user_id"]}, {"$unset": {"suspended": "", "suspended_reason": ""}})
    await db.security_flags.update_one({"id": flag_id}, {"$set": {"status": "resolved", "resolved_action": action, "resolved_at": datetime.now(timezone.utc).isoformat()}})
    return {"message": "Resolved"}

# ==================== PROFILE COMPLETENESS ====================

def compute_profile_completeness(user: dict) -> dict:
    checks = [
        ("photos", len(user.get("photos", [])) >= 3, 20),
        ("bio", len(user.get("bio") or "") >= 60, 15),
        ("intentions", bool(user.get("intentions")), 10),
        ("interests", len(user.get("interests", [])) >= 3, 10),
        ("personality_quiz", bool(user.get("quiz_complete")), 15),
        ("growth_goals", len(user.get("growth_goals", [])) >= 3, 10),
        ("icebreakers", len(user.get("icebreaker_answers", [])) >= 3, 10),
        ("verified", bool(user.get("video_verified") or user.get("photo_verified")), 10),
    ]
    pct = sum(weight for _, ok, weight in checks if ok)
    missing = [name for name, ok, _ in checks if not ok]
    return {"percent": pct, "missing": missing, "checks": [{"name": n, "complete": ok, "weight": w} for n, ok, w in checks]}

@api_router.get("/me/completeness")
async def my_completeness(user: dict = Depends(get_current_user)):
    return compute_profile_completeness(user)

# ==================== GROWTH GOALS + ICEBREAKERS + PLEDGE ====================

class GrowthGoalsPayload(BaseModel):
    goals: List[str]

class IcebreakersPayload(BaseModel):
    answers: List[Dict[str, str]]

GROWTH_GOAL_OPTIONS = [
    "Travel more", "Start a business", "Get fit", "Learn a language",
    "Buy a home", "Start a family", "Change careers", "Build wealth",
    "Run a marathon", "Write a book", "Master a creative skill", "Volunteer regularly"
]

ICEBREAKER_QUESTIONS = [
    "Best travel memory?", "Unpopular opinion?", "What's your love language?",
    "Best date you've ever been on?", "What are you currently obsessed with?",
    "Most spontaneous thing you've done?", "What's a hidden talent of yours?",
    "If you could only eat one cuisine forever?", "What show are you bingeing?",
    "What's a small thing that makes you happy?", "Sunday morning ritual?",
    "Last book that changed you?", "Karaoke song of choice?",
    "What's a hill you'd die on?", "Coolest place you've ever lived?",
    "If you had a free year, you'd...?", "Your most-used emoji?",
    "Beach person or mountain person?", "What's your unfair superpower?",
    "Childhood dream job?"
]

@api_router.get("/options/profile-fields")
async def get_profile_options():
    return {
        "growth_goal_options": GROWTH_GOAL_OPTIONS,
        "icebreaker_questions": ICEBREAKER_QUESTIONS,
        "filter_options": ADVANCED_FILTER_OPTIONS,
    }

# ==================== ADVANCED FILTERS ====================

ADVANCED_FILTER_OPTIONS = {
    "education": [
        {"value": "high_school", "label": "High school"},
        {"value": "associate", "label": "Associate"},
        {"value": "bachelor", "label": "Bachelor's"},
        {"value": "master", "label": "Master's"},
        {"value": "doctorate", "label": "Doctorate / PhD"},
        {"value": "trade", "label": "Trade / vocational"},
        {"value": "other", "label": "Other"},
    ],
    "body_type": [
        {"value": "slim", "label": "Slim"},
        {"value": "athletic", "label": "Athletic"},
        {"value": "average", "label": "Average"},
        {"value": "curvy", "label": "Curvy"},
        {"value": "plus", "label": "Plus"},
        {"value": "other", "label": "Other"},
    ],
    "drinking": [
        {"value": "never", "label": "Never"},
        {"value": "rarely", "label": "Rarely"},
        {"value": "socially", "label": "Socially"},
        {"value": "regularly", "label": "Regularly"},
        {"value": "sober", "label": "Sober"},
    ],
    "smoking": [
        {"value": "never", "label": "Never"},
        {"value": "sometimes", "label": "Sometimes"},
        {"value": "regularly", "label": "Regularly"},
        {"value": "trying_to_quit", "label": "Trying to quit"},
    ],
    "cannabis": [
        {"value": "never", "label": "Never"},
        {"value": "sometimes", "label": "Sometimes"},
        {"value": "regularly", "label": "Regularly"},
    ],
    "religion": [
        {"value": "christian", "label": "Christian"},
        {"value": "catholic", "label": "Catholic"},
        {"value": "muslim", "label": "Muslim"},
        {"value": "jewish", "label": "Jewish"},
        {"value": "hindu", "label": "Hindu"},
        {"value": "buddhist", "label": "Buddhist"},
        {"value": "spiritual", "label": "Spiritual"},
        {"value": "atheist", "label": "Atheist"},
        {"value": "agnostic", "label": "Agnostic"},
        {"value": "other", "label": "Other"},
    ],
    "politics": [
        {"value": "left", "label": "Left"},
        {"value": "center_left", "label": "Center-left"},
        {"value": "center", "label": "Center"},
        {"value": "center_right", "label": "Center-right"},
        {"value": "right", "label": "Right"},
        {"value": "apolitical", "label": "Apolitical"},
        {"value": "other", "label": "Other"},
    ],
    "has_kids": [
        {"value": "no", "label": "No kids"},
        {"value": "yes_living_with", "label": "Has kids (living with)"},
        {"value": "yes_not_living_with", "label": "Has kids (not living with)"},
        {"value": "prefer_not_say", "label": "Prefer not to say"},
    ],
    "wants_kids": [
        {"value": "yes", "label": "Wants kids"},
        {"value": "no", "label": "Doesn't want kids"},
        {"value": "maybe", "label": "Maybe"},
        {"value": "open", "label": "Open to it"},
    ],
    "exercise": [
        {"value": "daily", "label": "Daily"},
        {"value": "weekly", "label": "Weekly"},
        {"value": "sometimes", "label": "Sometimes"},
        {"value": "rarely", "label": "Rarely"},
        {"value": "never", "label": "Never"},
    ],
    "pets": [
        {"value": "dog", "label": "Dog"},
        {"value": "cat", "label": "Cat"},
        {"value": "bird", "label": "Bird"},
        {"value": "reptile", "label": "Reptile"},
        {"value": "fish", "label": "Fish"},
        {"value": "other", "label": "Other"},
        {"value": "none", "label": "None"},
    ],
}

ADVANCED_FILTER_KEYS = list(ADVANCED_FILTER_OPTIONS.keys())  # education, body_type, drinking, ...

class FilterPreferences(BaseModel):
    """User's saved discover filter prefs. Premium gates advanced fields."""
    # Always available (free)
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    distance_max: Optional[int] = None  # in the user's chosen unit (mi or km)
    recently_active_only: Optional[bool] = None  # active within last 24h
    # Premium
    height_cm_min: Optional[int] = None
    height_cm_max: Optional[int] = None
    education: List[str] = []
    body_type: List[str] = []
    drinking: List[str] = []
    smoking: List[str] = []
    cannabis: List[str] = []
    religion: List[str] = []
    politics: List[str] = []
    has_kids: List[str] = []
    wants_kids: List[str] = []
    exercise: List[str] = []
    pets: List[str] = []
    must_be_verified: Optional[bool] = None  # photo_verified OR video_verified
    must_have_personality_dna: Optional[bool] = None

FREE_FILTER_KEYS = {"age_min", "age_max", "distance_max", "recently_active_only"}

@api_router.get("/me/filters")
async def get_my_filters(user: dict = Depends(get_current_user)):
    return {
        "filters": user.get("filters") or {},
        "is_premium": user.get("subscription", "free") != "free",
        "advanced_keys": [k for k in ADVANCED_FILTER_KEYS] + ["height_cm_min", "height_cm_max", "must_be_verified", "must_have_personality_dna"],
        "free_keys": list(FREE_FILTER_KEYS),
    }

@api_router.put("/me/filters")
async def save_my_filters(payload: FilterPreferences, user: dict = Depends(get_current_user)):
    """Save filter prefs. Free users can save base filters; premium fields are silently ignored
    (or rejected) for free users to keep UX clear."""
    is_premium = user.get("subscription", "free") != "free"
    incoming = payload.model_dump(exclude_none=True)
    # Strip empty lists so we don't persist clutter
    incoming = {k: v for k, v in incoming.items() if not (isinstance(v, list) and len(v) == 0)}
    if not is_premium:
        # Drop premium-only keys silently — UI will gate them too
        incoming = {k: v for k, v in incoming.items() if k in FREE_FILTER_KEYS}
    # Validate ranges
    if "age_min" in incoming and incoming["age_min"] < 18:
        incoming["age_min"] = 18
    if "age_max" in incoming and incoming["age_max"] > 120:
        incoming["age_max"] = 120
    if "age_min" in incoming and "age_max" in incoming and incoming["age_min"] > incoming["age_max"]:
        raise HTTPException(status_code=400, detail="age_min must be ≤ age_max")
    if "height_cm_min" in incoming and "height_cm_max" in incoming and incoming["height_cm_min"] > incoming["height_cm_max"]:
        raise HTTPException(status_code=400, detail="height_cm_min must be ≤ height_cm_max")
    if "distance_max" in incoming and incoming["distance_max"] < 1:
        incoming["distance_max"] = 1
    await db.users.update_one({"id": user["id"]}, {"$set": {"filters": incoming}})
    return {"filters": incoming, "is_premium": is_premium}

@api_router.delete("/me/filters")
async def clear_my_filters(user: dict = Depends(get_current_user)):
    await db.users.update_one({"id": user["id"]}, {"$unset": {"filters": ""}})
    return {"filters": {}}

def _apply_advanced_filters_to_query(query: dict, user: dict) -> None:
    """Mutate the Mongo query with the user's advanced filters (DB-side filters only).
    Distance and recently-active filters that need computation are applied post-query."""
    f = user.get("filters") or {}
    is_premium = user.get("subscription", "free") != "free"
    # Age
    age_min = f.get("age_min")
    age_max = f.get("age_max")
    if age_min or age_max:
        age_q = {}
        if age_min: age_q["$gte"] = age_min
        if age_max: age_q["$lte"] = age_max
        query["age"] = age_q
    # Recently active
    if f.get("recently_active_only"):
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        query["last_active"] = {"$gte": cutoff}
    if not is_premium:
        return
    # Premium-only advanced filters
    if f.get("height_cm_min") or f.get("height_cm_max"):
        h = {}
        if f.get("height_cm_min"): h["$gte"] = f["height_cm_min"]
        if f.get("height_cm_max"): h["$lte"] = f["height_cm_max"]
        query["height_cm"] = h
    for field in ["education", "body_type", "drinking", "smoking", "cannabis", "religion", "politics", "has_kids", "wants_kids", "exercise"]:
        vals = f.get(field) or []
        if vals:
            query[field] = {"$in": vals}
    pets = f.get("pets") or []
    if pets:
        query["pets"] = {"$elemMatch": {"$in": pets}}
    if f.get("must_be_verified"):
        query["$and"] = query.get("$and", []) + [{"$or": [{"photo_verified": True}, {"video_verified": True}, {"selfie_verified": True}]}]
    if f.get("must_have_personality_dna"):
        query["personality_complete"] = True

def _apply_post_query_filters(profiles: list, user: dict) -> list:
    """Apply filters that need computed values (distance)."""
    f = user.get("filters") or {}
    dmax = f.get("distance_max")
    if dmax is not None and user.get("latitude") is not None and user.get("longitude") is not None:
        profiles = [p for p in profiles if (p.get("distance") is None or p.get("distance") <= dmax)]
    return profiles


@api_router.put("/me/growth-goals")
async def save_growth_goals(payload: GrowthGoalsPayload, user: dict = Depends(get_current_user)):
    goals = payload.goals[:5]
    await db.users.update_one({"id": user["id"]}, {"$set": {"growth_goals": goals}})
    return {"growth_goals": goals}

@api_router.put("/me/icebreakers")
async def save_icebreakers(payload: IcebreakersPayload, user: dict = Depends(get_current_user)):
    # Filter empty answers FIRST, then cap at 3
    valid = [{"question": a.get("question", ""), "answer": a.get("answer", "")} for a in payload.answers if a.get("answer", "").strip()]
    answers = valid[:3]
    await db.users.update_one({"id": user["id"]}, {"$set": {"icebreaker_answers": answers}})
    return {"icebreaker_answers": answers}

@api_router.put("/me/pledge")
async def toggle_pledge(payload: dict, user: dict = Depends(get_current_user)):
    enabled = bool(payload.get("enabled"))
    if enabled:
        await db.users.update_one({"id": user["id"]}, {"$set": {"anti_ghosting_pledge": True, "pledge_signed_at": datetime.now(timezone.utc).isoformat()}})
    else:
        await db.users.update_one({"id": user["id"]}, {"$set": {"anti_ghosting_pledge": False}, "$unset": {"pledge_signed_at": ""}})
    return {"anti_ghosting_pledge": enabled}

# ==================== WELLNESS MODE ====================

class WellnessCheckinPayload(BaseModel):
    mood: str  # "great", "good", "okay", "down", "frustrated"

class TakeBreakPayload(BaseModel):
    days: int  # 1-7

@api_router.post("/wellness/checkin")
async def wellness_checkin(payload: WellnessCheckinPayload, user: dict = Depends(get_current_user)):
    valid = ["great", "good", "okay", "down", "frustrated"]
    if payload.mood not in valid:
        raise HTTPException(status_code=400, detail=f"Mood must be one of {valid}")
    record = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "mood": payload.mood,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.wellness_checkins.insert_one(record)
    
    # Check if 3 negative moods in a row → show support
    last_three = await db.wellness_checkins.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).limit(3).to_list(3)
    show_support = len(last_three) >= 3 and all(c["mood"] in ("down", "frustrated") for c in last_three)
    return {
        "mood": payload.mood,
        "show_support": show_support,
        "support_message": "Dating can be tough. Try these: take a break, refresh your photos, and remember — your worth isn't measured by swipes." if show_support else None
    }

@api_router.get("/wellness/status")
async def wellness_status(user: dict = Depends(get_current_user)):
    today = datetime.now(timezone.utc).date().isoformat()
    today_checkin = await db.wellness_checkins.find_one({"user_id": user["id"], "created_at": {"$gte": today}}, {"_id": 0})
    paused_until = user.get("wellness_paused_until")
    is_paused = bool(paused_until and paused_until > datetime.now(timezone.utc).isoformat())
    return {
        "today_checkin": today_checkin,
        "paused_until": paused_until if is_paused else None,
        "is_paused": is_paused,
        "wellness_prompt_at": WELLNESS_PROMPT_AT,
        "daily_limit": FREE_DAILY_SWIPES if user.get("subscription") == "free" else None
    }

@api_router.post("/wellness/take-break")
async def take_break(payload: TakeBreakPayload, user: dict = Depends(get_current_user)):
    if payload.days < 1 or payload.days > 7:
        raise HTTPException(status_code=400, detail="Break must be between 1 and 7 days")
    until = (datetime.now(timezone.utc) + timedelta(days=payload.days)).isoformat()
    await db.users.update_one({"id": user["id"]}, {"$set": {"wellness_paused_until": until}})
    return {"paused_until": until, "message": f"Account paused for {payload.days} days. Your matches are preserved."}

@api_router.post("/wellness/resume")
async def resume_from_break(user: dict = Depends(get_current_user)):
    await db.users.update_one({"id": user["id"]}, {"$unset": {"wellness_paused_until": ""}})
    return {"message": "Welcome back!"}

# ==================== TRANSPARENCY SCORE ====================

def human_last_active(iso: Optional[str]) -> str:
    if not iso:
        return "Long ago"
    try:
        ts = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - ts
        secs = delta.total_seconds()
        if secs < 300:
            return "Active now"
        if secs < 3600:
            return f"Active {int(secs // 60)}m ago"
        if delta.days == 0:
            return f"Active {int(secs // 3600)}h ago"
        if delta.days == 1:
            return "Active yesterday"
        if delta.days < 7:
            return f"Active {delta.days}d ago"
        if delta.days < 30:
            return f"Active {delta.days // 7}w ago"
        return f"Active {delta.days // 30}mo ago"
    except Exception:
        return "Unknown"

def is_online_now(iso: Optional[str]) -> bool:
    """True if the user was active in the last 5 minutes."""
    if not iso:
        return False
    try:
        ts = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds() < 300
    except Exception:
        return False

async def compute_transparency(uid: str, profile: dict) -> dict:
    # Response rate: % of inbound matches where user has replied
    matches = await db.matches.find({"$or": [{"user1_id": uid}, {"user2_id": uid}]}).to_list(1000)
    matches_replied = 0
    matches_with_inbound = 0
    for m in matches:
        inbound = await db.messages.find_one({"match_id": m["id"], "sender_id": {"$ne": uid}})
        if inbound:
            matches_with_inbound += 1
            outbound = await db.messages.find_one({"match_id": m["id"], "sender_id": uid})
            if outbound:
                matches_replied += 1
    response_rate = round(100 * matches_replied / matches_with_inbound) if matches_with_inbound else None
    rr_badge = "High" if (response_rate or 0) >= 75 else "Medium" if (response_rate or 0) >= 40 else "Low" if response_rate is not None else "—"

    # Authenticity: photo_verified + bio + quiz + days_on_app
    authenticity = 0
    if profile.get("video_verified") or profile.get("photo_verified"): authenticity += 30
    if profile.get("selfie_verified"): authenticity += 10  # selfie photo badge
    if len(profile.get("bio") or "") >= 60: authenticity += 20
    if profile.get("quiz_complete"): authenticity += 20
    if profile.get("anti_ghosting_pledge"): authenticity += 10
    try:
        created = datetime.fromisoformat((profile.get("created_at") or "").replace("Z", "+00:00"))
        days_on_app = max(0, (datetime.now(timezone.utc) - created).days)
        if days_on_app >= 30: authenticity += 20
        elif days_on_app >= 7: authenticity += 10
    except Exception:
        days_on_app = 0

    # Genuine profile badge: active 30d + responsive
    genuine = days_on_app >= 30 and (response_rate or 0) >= 50

    # Match→date ratio (only computed for premium peers asking)
    return {
        "last_active_human": human_last_active(profile.get("last_active")),
        "response_rate": response_rate,
        "response_rate_badge": rr_badge,
        "authenticity_score": authenticity,
        "genuine_profile": genuine,
        "days_on_app": days_on_app
    }

@api_router.get("/transparency/{target_user_id}")
async def transparency(target_user_id: str, user: dict = Depends(get_current_user)):
    profile = await db.users.find_one({"id": target_user_id}, {"_id": 0, "password": 0, "email": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    return await compute_transparency(target_user_id, profile)

# ==================== DAILY MATCH HIGHLIGHT ====================

@api_router.get("/discover/todays-spark")
async def todays_spark(user: dict = Depends(get_current_user)):
    """The best single compat match for today, valid 24h."""
    # Cache today's pick on user record
    today = datetime.now(timezone.utc).date().isoformat()
    if user.get("todays_spark_date") == today and user.get("todays_spark_user_id"):
        pick = await db.users.find_one({"id": user["todays_spark_user_id"]}, {"_id": 0, "password": 0, "email": 0})
        if pick:
            return {"pick": pick, "date": today, "match_reasons": _why_reasons(user, pick)}
    
    # Compute: top profile from discover query, ranked by compatibility
    swiped = await db.swipes.find({"swiper_id": user["id"]}).to_list(10000)
    swiped_ids = [s["swiped_id"] for s in swiped] + [user["id"]] + user.get("blocked_users", [])
    looking_for = user.get("looking_for", "everyone")
    q = {"id": {"$nin": swiped_ids}, "profile_complete": True}
    if looking_for == "women": q["gender"] = "woman"
    elif looking_for == "men": q["gender"] = "man"
    elif looking_for != "everyone": q["gender"] = looking_for
    candidates = await db.users.find(q, {"_id": 0, "password": 0, "email": 0}).limit(50).to_list(50)
    if not candidates:
        return {"pick": None, "date": today}
    
    def score(c):
        s = 0
        # interests overlap
        my_int = set(user.get("interests", []))
        s += 10 * len(my_int & set(c.get("interests", [])))
        # growth goals overlap (Growth Match weighting)
        my_g = set(user.get("growth_goals", []))
        their_g = set(c.get("growth_goals", []))
        shared = len(my_g & their_g)
        s += 15 * shared
        if shared >= 3: s += 30  # big boost
        # languages overlap
        s += 5 * len(set(user.get("languages", [])) & set(c.get("languages", [])))
        # same intentions
        if user.get("intentions") and c.get("intentions") == user.get("intentions"): s += 20
        # photos + bio quality boost
        if (c.get("video_verified") or c.get("photo_verified")): s += 10
        if c.get("anti_ghosting_pledge"): s += 5
        return s
    
    candidates.sort(key=score, reverse=True)
    pick = candidates[0]
    await db.users.update_one({"id": user["id"]}, {"$set": {"todays_spark_user_id": pick["id"], "todays_spark_date": today}})
    return {"pick": pick, "date": today, "match_reasons": _why_reasons(user, pick)}

# ==================== WHY DID I SEE THIS MATCH? ====================

def _why_reasons(me: dict, them: dict) -> List[str]:
    reasons = []
    shared_int = set(me.get("interests", [])) & set(them.get("interests", []))
    if shared_int: reasons.append(f"You both love: {', '.join(list(shared_int)[:3])}")
    shared_g = set(me.get("growth_goals", [])) & set(them.get("growth_goals", []))
    if shared_g: reasons.append(f"Shared 2-year goals: {', '.join(list(shared_g)[:3])}")
    shared_lang = set(me.get("languages", [])) & set(them.get("languages", []))
    if shared_lang: reasons.append(f"Both speak: {', '.join(list(shared_lang)[:3])}")
    if me.get("intentions") and me.get("intentions") == them.get("intentions"):
        reasons.append(f"Same dating intention: {me.get('intentions')}")
    if them.get("anti_ghosting_pledge"): reasons.append("They signed the Anti-Ghosting Pledge")
    if them.get("video_verified") or them.get("photo_verified"): reasons.append("Their photos are verified")
    if not reasons: reasons.append("They match your basic preferences. Complete your profile to get smarter matches.")
    return reasons[:5]

@api_router.get("/discover/why/{target_user_id}")
async def why_this_match(target_user_id: str, user: dict = Depends(get_current_user)):
    them = await db.users.find_one({"id": target_user_id}, {"_id": 0, "password": 0, "email": 0})
    if not them:
        raise HTTPException(status_code=404, detail="Not found")
    return {"reasons": _why_reasons(user, them)}

# ==================== CONVERSATION HEALTH ====================

async def _conversation_health(match_id: str) -> dict:
    last = await db.messages.find_one({"match_id": match_id}, {"_id": 0}, sort=[("created_at", -1)])
    if not last:
        return {"status": "new", "color": "yellow", "hint": "Send the first message to break the ice!"}
    last_ts = datetime.fromisoformat(last["created_at"].replace("Z", "+00:00"))
    if last_ts.tzinfo is None:
        last_ts = last_ts.replace(tzinfo=timezone.utc)
    hours = (datetime.now(timezone.utc) - last_ts).total_seconds() / 3600
    count = await db.messages.count_documents({"match_id": match_id})
    if hours < 12 and count >= 4:
        return {"status": "active", "color": "green", "hint": "Conversation is flowing 🟢"}
    if hours < 48:
        return {"status": "slowing", "color": "yellow", "hint": "It's been a bit quiet. Try a fresh question."}
    return {"status": "stale", "color": "red", "hint": "Stale for 48h+ — time to reignite!"}

@api_router.get("/chat/{match_id}/health")
async def chat_health(match_id: str, user: dict = Depends(get_current_user)):
    match = await db.matches.find_one({"id": match_id})
    if not match or user["id"] not in [match["user1_id"], match["user2_id"]]:
        raise HTTPException(status_code=403, detail="Not your match")
    return await _conversation_health(match_id)

@api_router.post("/chat/{match_id}/reignite")
async def reignite_chat(match_id: str, user: dict = Depends(get_current_user)):
    match = await db.matches.find_one({"id": match_id})
    if not match or user["id"] not in [match["user1_id"], match["user2_id"]]:
        raise HTTPException(status_code=403, detail="Not your match")
    other_id = match["user2_id"] if match["user1_id"] == user["id"] else match["user1_id"]
    other = await db.users.find_one({"id": other_id}, {"_id": 0, "password": 0, "email": 0})
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"reignite-{match_id}-{datetime.now(timezone.utc).timestamp()}",
            system_message="""Give 3 fresh conversation restarters tailored to BOTH profiles. Each restarter is 1 sentence, playful, never cliché. Respond ONLY with raw JSON: {"topics": ["...", "...", "..."]}"""
        ).with_model("openai", "gpt-4o")
        msg = f"User A interests: {user.get('interests',[])}; intentions: {user.get('intentions')}; growth_goals: {user.get('growth_goals',[])}\nUser B interests: {other.get('interests',[])}; intentions: {other.get('intentions')}; growth_goals: {other.get('growth_goals',[])}"
        response = await chat.send_message(UserMessage(text=msg))
        data = extract_json(response)
        topics = data.get("topics") if isinstance(data, dict) else None
        if not isinstance(topics, list) or len(topics) != 3 or not all(isinstance(t, str) and t.strip() for t in topics):
            raise ValueError("LLM did not return exactly 3 topics")
        return {"topics": topics}
    except Exception as e:
        logger.error(f"Reignite error: {e}")
        return {"topics": [
            "What's something you'd do this weekend if every restaurant was closed?",
            "What podcast or playlist has been on rotation lately?",
            "If you could time-travel to one decade, which one and why?"
        ]}

# ==================== MATCH ANNIVERSARY ====================

@api_router.get("/match/{match_id}/anniversary")
async def match_anniversary(match_id: str, user: dict = Depends(get_current_user)):
    match = await db.matches.find_one({"id": match_id})
    if not match or user["id"] not in [match["user1_id"], match["user2_id"]]:
        raise HTTPException(status_code=403, detail="Not your match")
    created = datetime.fromisoformat(match["matched_at"].replace("Z", "+00:00")) if match.get("matched_at") else None
    if not created:
        return {"days": 0, "milestone": None}
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    days = (datetime.now(timezone.utc) - created).days
    milestone = None
    if 7 <= days <= 9:
        milestone = {"label": "1 week!", "message": "You matched a week ago — have you met yet? 🔥", "tier": "week"}
    elif 30 <= days <= 32:
        milestone = {"label": "30 days", "message": "Still sparking? 🎉", "tier": "month"}
    elif 90 <= days <= 92:
        milestone = {"label": "Spark Legend", "message": "90 days strong — you're a Spark Legend ⚡", "tier": "legend"}
    return {"days": days, "milestone": milestone}

# ==================== BATCH B: PERSONALITY DNA ====================

# 10 questions across the Big Five personality dimensions (OCEAN).
# Each choice contributes +1/-1/0 toward a trait, normalized 0-100.
PERSONALITY_QUESTIONS = [
    {"id": "q1", "text": "On a free weekend, you'd rather…", "trait": "extraversion",
     "choices": [{"id": "a", "text": "Throw a dinner party with friends", "score": 1},
                 {"id": "b", "text": "Cozy night in with a good book", "score": -1},
                 {"id": "c", "text": "Spontaneous adventure with one close friend", "score": 0}]},
    {"id": "q2", "text": "When making decisions you tend to…", "trait": "conscientiousness",
     "choices": [{"id": "a", "text": "Plan everything in a spreadsheet", "score": 1},
                 {"id": "b", "text": "Trust your gut and pivot if needed", "score": -1},
                 {"id": "c", "text": "Mix planning with intuition", "score": 0}]},
    {"id": "q3", "text": "Trying new food, you…", "trait": "openness",
     "choices": [{"id": "a", "text": "Order the weirdest thing on the menu", "score": 1},
                 {"id": "b", "text": "Stick to favorites that never disappoint", "score": -1},
                 {"id": "c", "text": "Let your date pick", "score": 0}]},
    {"id": "q4", "text": "After a disagreement, you usually…", "trait": "agreeableness",
     "choices": [{"id": "a", "text": "Apologize first, harmony matters", "score": 1},
                 {"id": "b", "text": "Stand your ground until they see your side", "score": -1},
                 {"id": "c", "text": "Take space, then talk it out calmly", "score": 0}]},
    {"id": "q5", "text": "Big life stress, you…", "trait": "neuroticism",
     "choices": [{"id": "a", "text": "Spiral a bit before bouncing back", "score": 1},
                 {"id": "b", "text": "Stay steady and tackle one thing at a time", "score": -1},
                 {"id": "c", "text": "Vent to someone close, then move on", "score": 0}]},
    {"id": "q6", "text": "Travel style is…", "trait": "openness",
     "choices": [{"id": "a", "text": "Backpack with zero itinerary", "score": 1},
                 {"id": "b", "text": "Curated hotel, every day pre-booked", "score": -1},
                 {"id": "c", "text": "Loose plan, room for serendipity", "score": 0}]},
    {"id": "q7", "text": "Your ideal partner energy is…", "trait": "extraversion",
     "choices": [{"id": "a", "text": "Life-of-the-party social butterfly", "score": 1},
                 {"id": "b", "text": "Calm, grounded, reflective", "score": -1},
                 {"id": "c", "text": "Selectively social — quality over quantity", "score": 0}]},
    {"id": "q8", "text": "Money mindset?", "trait": "conscientiousness",
     "choices": [{"id": "a", "text": "Saver. Future-proofed and budgeted", "score": 1},
                 {"id": "b", "text": "Treat-yourself. Memories > savings", "score": -1},
                 {"id": "c", "text": "50/50 — save and splurge in balance", "score": 0}]},
    {"id": "q9", "text": "In love, you value most…", "trait": "agreeableness",
     "choices": [{"id": "a", "text": "Emotional support and softness", "score": 1},
                 {"id": "b", "text": "Honest debate and challenge", "score": -1},
                 {"id": "c", "text": "Trust and shared values", "score": 0}]},
    {"id": "q10", "text": "Pressure brings out your…", "trait": "neuroticism",
     "choices": [{"id": "a", "text": "Anxious overthinking", "score": 1},
                 {"id": "b", "text": "Cool, focused clarity", "score": -1},
                 {"id": "c", "text": "Action-mode — just do it", "score": 0}]},
]

PERSONALITY_TRAITS = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]

def _archetype(dna: dict) -> str:
    """Friendly label based on dominant traits."""
    if not dna: return "Unmapped"
    o, c, e, a, n = dna.get("openness", 50), dna.get("conscientiousness", 50), dna.get("extraversion", 50), dna.get("agreeableness", 50), dna.get("neuroticism", 50)
    if o > 65 and e > 60: return "The Explorer"
    if c > 65 and a > 60: return "The Anchor"
    if e > 65 and a > 60: return "The Connector"
    if o > 65 and c > 60: return "The Visionary"
    if a > 65 and n < 40: return "The Harmonizer"
    if c > 65 and n < 40: return "The Steady Flame"
    if e < 40 and o > 60: return "The Quiet Creative"
    if n < 35: return "The Grounded One"
    return "The Balanced Soul"

class PersonalityAnswer(BaseModel):
    question_id: str
    choice_id: str

class PersonalityDNAPayload(BaseModel):
    answers: List[PersonalityAnswer]

@api_router.get("/personality/questions")
async def get_personality_questions():
    return {"questions": PERSONALITY_QUESTIONS, "traits": PERSONALITY_TRAITS}

@api_router.put("/personality/dna")
async def save_personality_dna(payload: PersonalityDNAPayload, user: dict = Depends(get_current_user)):
    # Build lookup
    q_map = {q["id"]: q for q in PERSONALITY_QUESTIONS}
    # Initialize raw trait sums and counts
    raw = {t: 0 for t in PERSONALITY_TRAITS}
    counts = {t: 0 for t in PERSONALITY_TRAITS}
    answered = {}
    for ans in payload.answers:
        q = q_map.get(ans.question_id)
        if not q: continue
        choice = next((c for c in q["choices"] if c["id"] == ans.choice_id), None)
        if not choice: continue
        raw[q["trait"]] += choice["score"]
        counts[q["trait"]] += 1
        answered[ans.question_id] = ans.choice_id
    if len(answered) < len(PERSONALITY_QUESTIONS):
        raise HTTPException(status_code=400, detail=f"Please answer all {len(PERSONALITY_QUESTIONS)} questions")
    # Normalize each trait from [-counts, +counts] to [0, 100]
    dna = {}
    for t in PERSONALITY_TRAITS:
        if counts[t] == 0:
            dna[t] = 50
        else:
            dna[t] = int(round(50 + (raw[t] / counts[t]) * 50))
            dna[t] = max(0, min(100, dna[t]))
    archetype = _archetype(dna)
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "personality_dna": dna,
            "personality_answers": answered,
            "personality_archetype": archetype,
            "personality_complete": True,
            "personality_completed_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    return {"personality_dna": dna, "archetype": archetype, "personality_complete": True}

@api_router.get("/personality/dna/{user_id}")
async def get_personality_dna(user_id: str, user: dict = Depends(get_current_user)):
    profile = await db.users.find_one({"id": user_id}, {"_id": 0, "personality_dna": 1, "personality_archetype": 1, "personality_complete": 1})
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "personality_dna": profile.get("personality_dna"),
        "archetype": profile.get("personality_archetype"),
        "personality_complete": profile.get("personality_complete", False),
    }

def _personality_score(me_dna: dict, them_dna: dict) -> int:
    """Compatibility 0-100 based on trait similarity, with a small complementary bonus for E/I."""
    if not me_dna or not them_dna: return 0
    total = 0
    for t in PERSONALITY_TRAITS:
        diff = abs(me_dna.get(t, 50) - them_dna.get(t, 50))
        # Closer = better; max diff 100 → 0pts, diff 0 → 100pts
        total += (100 - diff)
    avg = total / len(PERSONALITY_TRAITS)
    # Complementary bonus: opposite extraversion poles can still match well
    e_me = me_dna.get("extraversion", 50)
    e_them = them_dna.get("extraversion", 50)
    if (e_me > 65 and e_them < 40) or (e_them > 65 and e_me < 40):
        avg = min(100, avg + 5)
    return int(round(avg))

@api_router.get("/personality/compatibility/{target_user_id}")
async def personality_compat(target_user_id: str, user: dict = Depends(get_current_user)):
    target = await db.users.find_one({"id": target_user_id}, {"_id": 0, "id": 1, "personality_dna": 1, "personality_archetype": 1})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    me_dna = user.get("personality_dna")
    them_dna = target.get("personality_dna")
    if not me_dna or not them_dna:
        return {"score": None, "weighted_contribution": 0, "both_completed": False,
                "message": "Both users need to complete Personality DNA to unlock this score."}
    score = _personality_score(me_dna, them_dna)
    # Weighted contribution = 40% of overall match score
    return {
        "score": score,
        "weighted_contribution": int(round(score * 0.40)),
        "both_completed": True,
        "my_archetype": user.get("personality_archetype"),
        "their_archetype": target.get("personality_archetype"),
    }

# ==================== BATCH B: POST-DATE CHECK-IN ====================

class PostDateCheckin(BaseModel):
    match_id: str
    location: Optional[str] = None
    scheduled_time: datetime
    grace_minutes: int = 120  # auto-alert this many minutes after scheduled_time
    notes: Optional[str] = None

@api_router.post("/safety/post-date-checkin")
async def create_post_date_checkin(payload: PostDateCheckin, user: dict = Depends(get_current_user)):
    """Schedule a check-in. If user doesn't confirm safe within grace_minutes after scheduled_time, emergency contact is auto-notified."""
    if not user.get("emergency_contact_email") and not user.get("emergency_contact_phone"):
        raise HTTPException(status_code=400, detail="Add an emergency contact (email or phone) in Safety Settings first")
    sched = payload.scheduled_time
    if sched.tzinfo is None:
        sched = sched.replace(tzinfo=timezone.utc)
    auto_notify_at = sched + timedelta(minutes=max(15, min(720, payload.grace_minutes)))
    record = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "match_id": payload.match_id,
        "location": payload.location,
        "notes": payload.notes,
        "scheduled_time": sched.isoformat(),
        "grace_minutes": payload.grace_minutes,
        "auto_notify_at": auto_notify_at.isoformat(),
        "status": "scheduled",
        "alerted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.post_date_checkins.insert_one(record)
    return {"checkin_id": record["id"], "auto_notify_at": record["auto_notify_at"], "status": "scheduled"}

@api_router.post("/safety/post-date-checkin/{checkin_id}/confirm")
async def confirm_post_date_safe(checkin_id: str, user: dict = Depends(get_current_user)):
    res = await db.post_date_checkins.update_one(
        {"id": checkin_id, "user_id": user["id"]},
        {"$set": {"status": "confirmed_safe", "confirmed_at": datetime.now(timezone.utc).isoformat()}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Check-in not found")
    return {"message": "Glad you're safe! 💛", "status": "confirmed_safe"}

@api_router.post("/safety/post-date-checkin/{checkin_id}/snooze")
async def snooze_post_date(checkin_id: str, user: dict = Depends(get_current_user)):
    """Extend grace period by 30 minutes."""
    rec = await db.post_date_checkins.find_one({"id": checkin_id, "user_id": user["id"]})
    if not rec:
        raise HTTPException(status_code=404, detail="Check-in not found")
    if rec.get("status") != "scheduled":
        raise HTTPException(status_code=400, detail="Cannot snooze a completed check-in")
    new_notify = datetime.fromisoformat(rec["auto_notify_at"].replace("Z", "+00:00")) + timedelta(minutes=30)
    await db.post_date_checkins.update_one({"id": checkin_id}, {"$set": {"auto_notify_at": new_notify.isoformat()}})
    return {"auto_notify_at": new_notify.isoformat(), "snoozed": True}

@api_router.get("/safety/post-date-checkins")
async def list_post_date(user: dict = Depends(get_current_user)):
    items = await db.post_date_checkins.find({"user_id": user["id"]}, {"_id": 0}).sort("scheduled_time", -1).to_list(100)
    return {"checkins": items}

async def _sweep_post_date_alerts(user_id_filter: Optional[str] = None) -> dict:
    """Idempotent sweeper for overdue post-date check-ins. If user_id_filter is provided, only sweeps that user.
    Returns {'alerted': N, 'checked': M, 'pushed': K}."""
    now = datetime.now(timezone.utc)
    query = {"status": "scheduled", "alerted": False}
    if user_id_filter:
        query["user_id"] = user_id_filter
    pending = await db.post_date_checkins.find(query).to_list(500)
    alerted = 0
    pushed = 0
    for rec in pending:
        try:
            notify_at = datetime.fromisoformat(rec["auto_notify_at"].replace("Z", "+00:00"))
        except Exception:
            continue
        if notify_at > now:
            continue
        owner = await db.users.find_one({"id": rec["user_id"]})
        if not owner:
            continue
        to_email = owner.get("emergency_contact_email")
        contact_name = owner.get("emergency_contact_name") or "Friend"
        if to_email:
            subject = f"[Spark Safety] {owner.get('name', 'Your contact')} hasn't checked in"
            html = f"""<div style='font-family:system-ui,sans-serif;max-width:560px'>
<h2 style='color:#FF2E63'>Spark Safety Alert</h2>
<p>Hi {contact_name},</p>
<p><b>{owner.get('name','Your friend')}</b> set a date check-in that has not been confirmed.</p>
<ul>
<li><b>Scheduled:</b> {rec.get('scheduled_time','—')}</li>
<li><b>Location:</b> {rec.get('location') or 'not shared'}</li>
<li><b>Notes:</b> {rec.get('notes') or '—'}</li>
</ul>
<p>Please reach out to check on them. If you're unable to reach them and are concerned for their safety, contact local emergency services.</p>
<p style='color:#888;font-size:12px'>Sent automatically by Spark because you're their emergency contact.</p>
</div>"""
            asyncio.create_task(send_email(to_email, subject, html))
        # Also push the owner a strong reminder before alerting contact (a final nudge)
        try:
            await push_notify_user(owner["id"], "Check-in needed", "Tap to confirm you're safe — we're about to alert your emergency contact.", url="/safety/post-date-checkin")
            pushed += 1
        except Exception as e:
            logger.warning(f"Push during sweep failed: {e}")
        await db.post_date_checkins.update_one(
            {"id": rec["id"]},
            {"$set": {"alerted": True, "alerted_at": now.isoformat(), "status": "alerted"}}
        )
        alerted += 1
    return {"alerted": alerted, "checked": len(pending), "pushed": pushed}

@api_router.post("/safety/run-post-date-alerts")
async def run_post_date_alerts(user: dict = Depends(get_current_user)):
    """Manual trigger (still public for owner-triggered sweep). The background scheduler runs the same sweep every 5 minutes for ALL users."""
    res = await _sweep_post_date_alerts(user_id_filter=user["id"])
    return res

# ==================== BATCH B: SAFE MEETING ZONES ====================

# Seeded list of generic safe public meeting spots. In production, this would be backed by
# a verified venues database with admin moderation.
SAFE_ZONES_SEED = [
    {"id": "sz1", "name": "Local Public Library", "category": "library", "safety_rating": 5, "tips": "Well-lit, quiet, security present", "lat": None, "lng": None, "city": None},
    {"id": "sz2", "name": "Major Chain Coffee Shop", "category": "cafe", "safety_rating": 4, "tips": "Public, busy, cameras", "lat": None, "lng": None, "city": None},
    {"id": "sz3", "name": "City Park Main Entrance", "category": "park", "safety_rating": 4, "tips": "Daytime only, near foot traffic", "lat": None, "lng": None, "city": None},
    {"id": "sz4", "name": "Shopping Mall Food Court", "category": "mall", "safety_rating": 5, "tips": "Crowded, security present", "lat": None, "lng": None, "city": None},
    {"id": "sz5", "name": "Museum Lobby", "category": "museum", "safety_rating": 5, "tips": "Public, ticketed entry, staff present", "lat": None, "lng": None, "city": None},
    {"id": "sz6", "name": "Bookstore Cafe", "category": "cafe", "safety_rating": 4, "tips": "Public, quiet, easy exit", "lat": None, "lng": None, "city": None},
    {"id": "sz7", "name": "Hotel Lobby Lounge", "category": "hotel", "safety_rating": 5, "tips": "Concierge desk, cameras, neutral ground", "lat": None, "lng": None, "city": None},
    {"id": "sz8", "name": "Farmers Market Square", "category": "market", "safety_rating": 4, "tips": "Daytime, lots of people", "lat": None, "lng": None, "city": None},
    {"id": "sz9", "name": "Botanical Garden", "category": "park", "safety_rating": 4, "tips": "Ticketed, daytime only", "lat": None, "lng": None, "city": None},
    {"id": "sz10", "name": "Bowling Alley", "category": "entertainment", "safety_rating": 4, "tips": "Public, active environment, staff present", "lat": None, "lng": None, "city": None},
    {"id": "sz11", "name": "Art Gallery Opening", "category": "culture", "safety_rating": 4, "tips": "Public event, busy", "lat": None, "lng": None, "city": None},
    {"id": "sz12", "name": "Ice Cream Parlor", "category": "cafe", "safety_rating": 4, "tips": "Short, sweet, low-pressure first date", "lat": None, "lng": None, "city": None},
    {"id": "sz13", "name": "Brunch Spot (Daytime)", "category": "restaurant", "safety_rating": 4, "tips": "Daylight, public, neutral", "lat": None, "lng": None, "city": None},
    {"id": "sz14", "name": "Mini Golf Course", "category": "entertainment", "safety_rating": 4, "tips": "Activity-based, low-stakes", "lat": None, "lng": None, "city": None},
    {"id": "sz15", "name": "Public Beach (Daytime)", "category": "outdoor", "safety_rating": 3, "tips": "Daytime, populated area only", "lat": None, "lng": None, "city": None},
]

@api_router.get("/safety/zones")
async def safe_zones(city: Optional[str] = None, lat: Optional[float] = None, lng: Optional[float] = None, user: dict = Depends(get_current_user)):
    """Return curated safe public meeting spots. If city or coords given, attach a context label."""
    zones = [dict(z) for z in SAFE_ZONES_SEED]
    if city:
        for z in zones:
            z["city"] = city
    if lat is not None and lng is not None:
        for z in zones:
            z["near_user"] = True
    return {"zones": zones, "guidance": [
        "Meet in a public place for the first 3 dates",
        "Tell a trusted friend where you'll be",
        "Arrange your own transport — don't get picked up at home",
        "Stay sober enough to make safe decisions",
        "Trust your gut — leave if anything feels off"
    ]}

class LocationSharePayload(BaseModel):
    match_id: str
    latitude: float
    longitude: float
    duration_minutes: int = 60  # share for this long

@api_router.post("/safety/share-location")
async def share_location(payload: LocationSharePayload, user: dict = Depends(get_current_user)):
    # Verify match
    m = await db.matches.find_one({"id": payload.match_id})
    if not m or user["id"] not in [m["user1_id"], m["user2_id"]]:
        raise HTTPException(status_code=403, detail="Not your match")
    duration = max(15, min(240, payload.duration_minutes))
    expires_dt = datetime.now(timezone.utc) + timedelta(minutes=duration)
    record = {
        "user_id": user["id"],
        "match_id": payload.match_id,
        "latitude": payload.latitude,
        "longitude": payload.longitude,
        "expires_at": expires_dt,  # BSON datetime — TTL index will purge automatically
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.location_shares.update_one(
        {"user_id": user["id"], "match_id": payload.match_id},
        {"$set": record},
        upsert=True
    )
    return {"shared": True, "expires_at": expires_dt.isoformat()}

@api_router.get("/safety/share-location/{match_id}")
async def get_shared_location(match_id: str, user: dict = Depends(get_current_user)):
    m = await db.matches.find_one({"id": match_id})
    if not m or user["id"] not in [m["user1_id"], m["user2_id"]]:
        raise HTTPException(status_code=403, detail="Not your match")
    other_id = m["user2_id"] if m["user1_id"] == user["id"] else m["user1_id"]
    share = await db.location_shares.find_one({"user_id": other_id, "match_id": match_id}, {"_id": 0})
    if not share:
        return {"sharing": False}
    expires_raw = share.get("expires_at")
    # Backwards-compat: was previously stored as ISO string
    if isinstance(expires_raw, str):
        expires = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
    else:
        expires = expires_raw
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        return {"sharing": False, "expired": True}
    return {"sharing": True, "latitude": share["latitude"], "longitude": share["longitude"], "expires_at": expires.isoformat(), "updated_at": share.get("updated_at")}

@api_router.delete("/safety/share-location/{match_id}")
async def stop_sharing(match_id: str, user: dict = Depends(get_current_user)):
    await db.location_shares.delete_one({"user_id": user["id"], "match_id": match_id})
    return {"sharing": False}

# ==================== BATCH B: VERIFIED PHOTO BADGE (SELFIE) ====================

class SelfieVerifyPayload(BaseModel):
    selfie_data_url: str  # base64 selfie

@api_router.post("/profile/selfie-verify")
async def selfie_verify(payload: SelfieVerifyPayload, user: dict = Depends(get_current_user)):
    """Compare a live selfie to the user's primary profile photo using GPT-4o vision.
    On match → selfie_verified=True + selfie_verified_at."""
    photos = user.get("photos") or []
    if not photos:
        raise HTTPException(status_code=400, detail="Add a profile photo first")
    primary_photo = photos[0]
    if not payload.selfie_data_url.startswith("data:image/"):
        raise HTTPException(status_code=400, detail="Selfie must be a data URL")
    # Conservative size cap to keep LLM call cheap
    if len(payload.selfie_data_url) > 2_500_000:  # ~1.8MB after base64
        raise HTTPException(status_code=400, detail="Selfie image too large (max ~1.8MB)")
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"selfie-{user['id']}-{datetime.now(timezone.utc).timestamp()}",
            system_message=(
                "You compare two photos and decide if they show the same real human. "
                "You are NOT identifying anyone — only judging visual similarity for a dating app's "
                "photo-verification badge. Respond ONLY with raw JSON: "
                '{"match": true|false, "confidence": 0-100, "reason": "short reason"}'
            )
        ).with_model("openai", "gpt-4o")
        prompt_text = (
            "Photo 1 (profile photo URL): " + primary_photo + "\n"
            "Photo 2 (selfie data URL): " + payload.selfie_data_url[:120] + "...(truncated)\n"
            "Compare overall facial structure, hair, and general appearance. "
            "Profile may be a different angle or lighting. If you can't see a clear human face in either, return match=false."
        )
        # Vision: send both as image parts when SDK supports; otherwise this is a textual heuristic.
        response = await chat.send_message(UserMessage(text=prompt_text))
        data = extract_json(response)
        verified = bool(data.get("match")) and int(data.get("confidence", 0)) >= 60
    except Exception as e:
        logger.error(f"Selfie verify LLM error: {e}")
        # Conservative: do not auto-verify on failure
        verified = False
        data = {"match": False, "confidence": 0, "reason": "Verification service unavailable. Try again later."}
    update = {"selfie_verified_at": datetime.now(timezone.utc).isoformat()}
    if verified:
        update["selfie_verified"] = True
        update["photo_verified"] = True
    await db.users.update_one({"id": user["id"]}, {"$set": update})
    return {
        "verified": verified,
        "confidence": int(data.get("confidence", 0)),
        "reason": data.get("reason", ""),
    }

# ==================== BATCH B: BACKGROUND LITE CHECK ====================

class BackgroundLitePayload(BaseModel):
    full_legal_name: str
    date_of_birth: str  # YYYY-MM-DD
    country: str
    id_last4: Optional[str] = None  # last 4 of any government ID (optional)

@api_router.post("/profile/background-lite")
async def background_lite_check(payload: BackgroundLitePayload, user: dict = Depends(get_current_user)):
    """Lightweight identity attestation. Stores a hashed record of the name+dob and grants a
    'Background Lite ✓' badge. Real third-party check (e.g. Checkr) can be wired here later."""
    if not payload.full_legal_name or not payload.full_legal_name.strip():
        raise HTTPException(status_code=400, detail="Full legal name is required")
    if not payload.country or not payload.country.strip():
        raise HTTPException(status_code=400, detail="Country is required")
    # Validate DOB and age
    try:
        dob = datetime.strptime(payload.date_of_birth, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="DOB must be YYYY-MM-DD")
    today = datetime.now(timezone.utc).date()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if age < 18:
        raise HTTPException(status_code=400, detail="You must be 18 or older")
    # Store a non-reversible hash of identifying info — actual PII isn't kept in plaintext
    import hashlib
    identity_hash = hashlib.sha256(f"{payload.full_legal_name.strip().lower()}|{payload.date_of_birth}|{payload.country.upper()}".encode()).hexdigest()
    record = {
        "user_id": user["id"],
        "identity_hash": identity_hash,
        "country": payload.country.upper(),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "id_last4": payload.id_last4,
    }
    await db.background_checks.update_one(
        {"user_id": user["id"]},
        {"$set": record},
        upsert=True
    )
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "background_lite_verified": True,
            "background_lite_verified_at": record["verified_at"],
            "background_lite_country": payload.country.upper(),
        }}
    )
    return {"verified": True, "badge": "Background Lite ✓", "verified_at": record["verified_at"]}

@api_router.get("/profile/badges/{user_id}")
async def get_badges(user_id: str, user: dict = Depends(get_current_user)):
    """All verification badges a user has earned, for display on their profile."""
    p = await db.users.find_one({"id": user_id}, {"_id": 0, "video_verified": 1, "photo_verified": 1, "selfie_verified": 1, "background_lite_verified": 1, "quiz_complete": 1, "personality_complete": 1, "anti_ghosting_pledge": 1})
    if not p:
        raise HTTPException(status_code=404, detail="User not found")
    badges = []
    if p.get("selfie_verified") or p.get("photo_verified"): badges.append({"id": "photo_verified", "label": "Photo Verified", "tier": "trust"})
    if p.get("video_verified"): badges.append({"id": "video_verified", "label": "Video Verified", "tier": "trust"})
    if p.get("background_lite_verified"): badges.append({"id": "background_lite", "label": "Background Lite ✓", "tier": "trust"})
    if p.get("personality_complete"): badges.append({"id": "personality_dna", "label": "Personality DNA Mapped", "tier": "compatibility"})
    if p.get("quiz_complete"): badges.append({"id": "vibe_quiz", "label": "Vibe Quiz Done", "tier": "compatibility"})
    if p.get("anti_ghosting_pledge"): badges.append({"id": "anti_ghosting", "label": "Anti-Ghosting Pledge", "tier": "values"})
    return {"badges": badges}

# ==================== BATCH C: COMPATIBILITY TIMELINE ====================

@api_router.get("/match/{match_id}/timeline")
async def compatibility_timeline(match_id: str, user: dict = Depends(get_current_user)):
    """AI-predicted relationship milestones for a match, based on both profiles + DNA + intentions."""
    match = await db.matches.find_one({"id": match_id})
    if not match or user["id"] not in [match["user1_id"], match["user2_id"]]:
        raise HTTPException(status_code=403, detail="Not your match")
    # Cache: same match → same timeline for 7 days
    cached = await db.compat_timelines.find_one({"match_id": match_id})
    if cached:
        cached_at = datetime.fromisoformat(cached["generated_at"].replace("Z", "+00:00"))
        if (datetime.now(timezone.utc) - cached_at).days < 7:
            return {"milestones": cached["milestones"], "generated_at": cached["generated_at"], "cached": True}

    other_id = match["user2_id"] if match["user1_id"] == user["id"] else match["user1_id"]
    other = await db.users.find_one({"id": other_id}, {"_id": 0, "password": 0, "email": 0})
    if not other:
        raise HTTPException(status_code=404, detail="Match user missing")

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"timeline-{match_id}",
            system_message=(
                "You generate a realistic, encouraging relationship-milestone timeline for two daters who just matched. "
                "Use their interests, intentions, growth goals, and Big-Five personality DNA to predict 6 milestones. "
                "Each milestone has: title (short), estimated_window (e.g. 'Week 1', 'Month 2'), why (one sentence), confidence (low/medium/high). "
                'Respond ONLY with raw JSON: {"milestones":[{"title":"","estimated_window":"","why":"","confidence":""}, ...6 items]}'
            )
        ).with_model("openai", "gpt-4o")
        body = (
            f"User A: interests={user.get('interests',[])}; intentions={user.get('intentions')}; goals={user.get('growth_goals',[])}; dna={user.get('personality_dna',{})}\n"
            f"User B: interests={other.get('interests',[])}; intentions={other.get('intentions')}; goals={other.get('growth_goals',[])}; dna={other.get('personality_dna',{})}"
        )
        response = await chat.send_message(UserMessage(text=body))
        data = extract_json(response)
        milestones = data.get("milestones") if isinstance(data, dict) else None
        if not isinstance(milestones, list) or len(milestones) < 4:
            raise ValueError("Invalid milestone list")
        # Sanitize each milestone
        cleaned = []
        for m in milestones[:6]:
            cleaned.append({
                "title": str(m.get("title", "Milestone"))[:80],
                "estimated_window": str(m.get("estimated_window", ""))[:40],
                "why": str(m.get("why", ""))[:200],
                "confidence": (m.get("confidence") or "medium").lower() if str(m.get("confidence","")).lower() in ("low","medium","high") else "medium",
            })
        milestones = cleaned
    except Exception as e:
        logger.error(f"Timeline LLM error: {e}")
        milestones = [
            {"title": "First real conversation", "estimated_window": "Week 1", "why": "Both of you have strong communication interests.", "confidence": "high"},
            {"title": "First voice or video call", "estimated_window": "Week 1-2", "why": "Builds trust before meeting in person.", "confidence": "medium"},
            {"title": "First in-person date", "estimated_window": "Week 2-3", "why": "Aligned intentions and shared interests.", "confidence": "high"},
            {"title": "Decide on exclusivity", "estimated_window": "Month 2-3", "why": "Both signaled long-term intent.", "confidence": "medium"},
            {"title": "Meet each other's close friends", "estimated_window": "Month 3-4", "why": "Natural next step for serious daters.", "confidence": "medium"},
            {"title": "First weekend trip together", "estimated_window": "Month 4-6", "why": "Test compatibility in a relaxed setting.", "confidence": "low"},
        ]
    record = {
        "match_id": match_id,
        "milestones": milestones,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.compat_timelines.update_one({"match_id": match_id}, {"$set": record}, upsert=True)
    return {"milestones": milestones, "generated_at": record["generated_at"], "cached": False}

# ==================== BATCH C: FIRST DATE SCRIPT ====================

@api_router.get("/chat/{match_id}/first-date-script")
async def first_date_script(match_id: str, user: dict = Depends(get_current_user)):
    """AI conversation guide for the first IRL date. Unlocks after 10+ messages exchanged."""
    match = await db.matches.find_one({"id": match_id})
    if not match or user["id"] not in [match["user1_id"], match["user2_id"]]:
        raise HTTPException(status_code=403, detail="Not your match")
    msg_count = await db.messages.count_documents({"match_id": match_id})
    if msg_count < 10:
        return {"unlocked": False, "messages_needed": 10 - msg_count, "messages_so_far": msg_count}

    # Cache for 24h per match
    cached = await db.first_date_scripts.find_one({"match_id": match_id})
    if cached:
        cached_at = datetime.fromisoformat(cached["generated_at"].replace("Z", "+00:00"))
        if (datetime.now(timezone.utc) - cached_at).total_seconds() < 24 * 3600:
            return {"unlocked": True, "script": cached["script"], "generated_at": cached["generated_at"], "cached": True}

    other_id = match["user2_id"] if match["user1_id"] == user["id"] else match["user1_id"]
    other = await db.users.find_one({"id": other_id}, {"_id": 0, "password": 0, "email": 0})
    if not other:
        raise HTTPException(status_code=404, detail="Match user missing")

    # Grab last 15 messages for context (decrypted by middleware/service in main /messages, but for raw access we'll just use counts/interests)
    recent = await db.messages.find({"match_id": match_id}, {"_id": 0, "content": 1}).sort("created_at", -1).limit(15).to_list(15)
    snippet = " | ".join([m.get("content", "")[:120] for m in recent if m.get("content")])

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"first-date-script-{match_id}",
            system_message=(
                "You write a friendly first-date conversation guide for ONE of the two daters. Output strict JSON: "
                '{"openers":["..","..","..",".."],"deeper_questions":["..","..","..",".."],"topics_to_avoid":["..","..",".."],"venue_suggestions":[{"name":"..","why":".."},{"name":"..","why":".."},{"name":"..","why":".."}],"tone":".."}'
                " Tailor everything to both profiles. Keep each item concise and actionable. Tone is one short sentence describing the vibe to aim for."
            )
        ).with_model("openai", "gpt-4o")
        body = (
            f"Me: interests={user.get('interests',[])}; intentions={user.get('intentions')}; goals={user.get('growth_goals',[])}; dna={user.get('personality_dna',{})}\n"
            f"Them: interests={other.get('interests',[])}; intentions={other.get('intentions')}; goals={other.get('growth_goals',[])}; dna={other.get('personality_dna',{})}\n"
            f"Conversation so far (most recent 15): {snippet[:1500]}"
        )
        response = await chat.send_message(UserMessage(text=body))
        data = extract_json(response)
        # Validate shape minimally
        required_keys = {"openers", "deeper_questions", "topics_to_avoid", "venue_suggestions", "tone"}
        if not isinstance(data, dict) or not required_keys.issubset(set(data.keys())):
            raise ValueError("Invalid script shape")
        script = {
            "openers": [str(x)[:160] for x in (data.get("openers") or [])][:4],
            "deeper_questions": [str(x)[:200] for x in (data.get("deeper_questions") or [])][:4],
            "topics_to_avoid": [str(x)[:160] for x in (data.get("topics_to_avoid") or [])][:3],
            "venue_suggestions": [
                {"name": str((v or {}).get("name", ""))[:80], "why": str((v or {}).get("why", ""))[:200]}
                for v in (data.get("venue_suggestions") or [])
            ][:3],
            "tone": str(data.get("tone", ""))[:200],
        }
    except Exception as e:
        logger.error(f"First-date script LLM error: {e}")
        script = {
            "openers": [
                "What's been the highlight of your week so far?",
                "Anything you've been geeking out about lately?",
                "What's the last thing that made you laugh out loud?",
                "If we got bored here, where would you wanna go next?",
            ],
            "deeper_questions": [
                "What does a really good year look like for you?",
                "What's something you used to believe that you've changed your mind on?",
                "Who's been the biggest influence on how you live now?",
                "What do you want more of in your life right now?",
            ],
            "topics_to_avoid": [
                "Heavy ex talk before dessert",
                "Career-ladder comparisons",
                "Politics until you know each other better",
            ],
            "venue_suggestions": [
                {"name": "Quiet wine bar or specialty coffee shop", "why": "Calm enough to hear each other, not too long if vibes are off."},
                {"name": "Walk through a park or city neighborhood", "why": "Movement keeps conversation flowing and lowers awkwardness."},
                {"name": "Casual share-plates restaurant", "why": "Shared food = easy bonding without the pressure of a long dinner."},
            ],
            "tone": "Curious, warm, low-stakes. Aim to leave them wanting one more conversation.",
        }
    record = {
        "match_id": match_id,
        "script": script,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.first_date_scripts.update_one({"match_id": match_id}, {"$set": record}, upsert=True)
    return {"unlocked": True, "script": script, "generated_at": record["generated_at"], "cached": False}

# ==================== BATCH C: WEEKLY SPARK CHALLENGE ====================

# Rotating pool of weekly challenges. Each Monday a deterministic rotation picks the active one.
WEEKLY_CHALLENGES = [
    {"id": "wc1", "title": "Send a Bold Opener", "description": "Send the first message to a new match using something specific from their profile.", "xp": 50, "cta": "Send opener", "verb": "open"},
    {"id": "wc2", "title": "Match Reignite", "description": "Reignite a stale chat that's been quiet for 48+ hours.", "xp": 60, "cta": "Reignite", "verb": "reignite"},
    {"id": "wc3", "title": "Verify Yourself", "description": "Complete selfie verification this week.", "xp": 80, "cta": "Verify selfie", "verb": "verify_photo"},
    {"id": "wc4", "title": "Map Your DNA", "description": "Complete the Personality DNA test.", "xp": 100, "cta": "Take DNA test", "verb": "personality_dna"},
    {"id": "wc5", "title": "Plan a Real Date", "description": "Schedule a Post-Date Check-in with an emergency contact.", "xp": 70, "cta": "Schedule", "verb": "schedule_date"},
    {"id": "wc6", "title": "Be Vulnerable", "description": "Answer 3 Icebreaker prompts on your profile.", "xp": 50, "cta": "Add icebreakers", "verb": "icebreakers"},
    {"id": "wc7", "title": "Sign the Pledge", "description": "Sign the Anti-Ghosting Pledge.", "xp": 40, "cta": "Sign pledge", "verb": "pledge"},
    {"id": "wc8", "title": "Wellness Check", "description": "Do your daily mood check-in for 5 days this week.", "xp": 60, "cta": "Check-in", "verb": "wellness"},
    {"id": "wc9", "title": "Growth Mode", "description": "Add your top 3 growth goals to your profile.", "xp": 50, "cta": "Set goals", "verb": "growth_goals"},
    {"id": "wc10", "title": "Background Lite", "description": "Complete the Background Lite identity check.", "xp": 90, "cta": "Verify", "verb": "background_lite"},
    {"id": "wc11", "title": "Tour the Promise", "description": "Read the Our Promise + Algorithm Transparency pages.", "xp": 30, "cta": "Read", "verb": "promise"},
    {"id": "wc12", "title": "Compliment, Don't Compare", "description": "Send a sincere compliment to one match (not about their looks).", "xp": 60, "cta": "Send compliment", "verb": "compliment"},
]

def _current_week_key() -> str:
    """ISO year-week, e.g. '2026-W08'. Resets every Monday UTC."""
    now = datetime.now(timezone.utc)
    iso = now.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"

def _active_challenge() -> dict:
    """Pick a challenge based on ISO week number — deterministic rotation."""
    now = datetime.now(timezone.utc)
    idx = now.isocalendar().week % len(WEEKLY_CHALLENGES)
    return WEEKLY_CHALLENGES[idx]

def _xp_to_level(xp: int) -> dict:
    """Convert XP to level using a gentle curve."""
    # 100 XP/level for first 5 levels, then +50/level
    levels = [0, 100, 200, 300, 400, 500, 650, 800, 1000, 1250, 1500, 1850, 2250, 2700]
    level = 0
    for i, threshold in enumerate(levels):
        if xp >= threshold:
            level = i
    next_threshold = levels[min(level + 1, len(levels) - 1)] if level + 1 < len(levels) else levels[-1] + 500
    return {
        "level": level,
        "xp_current": xp,
        "xp_for_next": next_threshold,
        "xp_in_level": xp - (levels[level] if level < len(levels) else levels[-1]),
        "xp_needed_for_next": next_threshold - xp,
    }

@api_router.get("/challenges/weekly")
async def get_weekly_challenge(user: dict = Depends(get_current_user)):
    """Current week's challenge + the user's progress, XP, level, and badges."""
    week_key = _current_week_key()
    challenge = _active_challenge()
    completion = await db.challenge_completions.find_one({
        "user_id": user["id"],
        "challenge_id": challenge["id"],
        "week_key": week_key,
    })
    xp = user.get("xp", 0)
    streak = user.get("streak_weeks", 0)
    badges = user.get("challenge_badges", [])
    return {
        "week_key": week_key,
        "challenge": challenge,
        "completed": bool(completion),
        "completed_at": completion["completed_at"] if completion else None,
        "xp": xp,
        "level_info": _xp_to_level(xp),
        "streak_weeks": streak,
        "badges": badges,
    }

@api_router.post("/challenges/{challenge_id}/complete")
async def complete_challenge(challenge_id: str, user: dict = Depends(get_current_user)):
    """Mark a challenge complete and award XP. Only the current active challenge counts toward the weekly streak."""
    challenge = next((c for c in WEEKLY_CHALLENGES if c["id"] == challenge_id), None)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    active = _active_challenge()
    is_active = challenge_id == active["id"]
    week_key = _current_week_key()

    existing = await db.challenge_completions.find_one({
        "user_id": user["id"],
        "challenge_id": challenge_id,
        "week_key": week_key,
    })
    if existing:
        return {"already_completed": True, "xp": user.get("xp", 0), "level_info": _xp_to_level(user.get("xp", 0))}

    award_xp = challenge["xp"]
    await db.challenge_completions.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "challenge_id": challenge_id,
        "week_key": week_key,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "xp_awarded": award_xp,
        "was_active_week": is_active,
    })

    new_xp = user.get("xp", 0) + award_xp
    update = {"xp": new_xp}
    new_badges = list(user.get("challenge_badges") or [])

    # Update streak only for active weekly challenge
    streak = user.get("streak_weeks", 0)
    last_streak_week = user.get("last_streak_week")
    if is_active:
        # If user completed last week's challenge, increment; otherwise reset to 1
        now = datetime.now(timezone.utc)
        last_week_iso = (now - timedelta(weeks=1)).isocalendar()
        last_week_key = f"{last_week_iso.year}-W{last_week_iso.week:02d}"
        if last_streak_week == last_week_key:
            streak += 1
        else:
            streak = 1
        update["streak_weeks"] = streak
        update["last_streak_week"] = week_key

        # Streak-based badges
        if streak == 4 and "Month of Sparks" not in new_badges: new_badges.append("Month of Sparks")
        if streak == 12 and "Quarter Champion" not in new_badges: new_badges.append("Quarter Champion")
        if streak == 52 and "Spark Year-One" not in new_badges: new_badges.append("Spark Year-One")

    # Level-based badges
    lvl = _xp_to_level(new_xp)["level"]
    if lvl >= 5 and "Rising Spark" not in new_badges: new_badges.append("Rising Spark")
    if lvl >= 10 and "Spark Pro" not in new_badges: new_badges.append("Spark Pro")

    if new_badges != (user.get("challenge_badges") or []):
        update["challenge_badges"] = new_badges

    await db.users.update_one({"id": user["id"]}, {"$set": update})
    return {
        "completed": True,
        "xp_awarded": award_xp,
        "xp": new_xp,
        "level_info": _xp_to_level(new_xp),
        "streak_weeks": streak if is_active else user.get("streak_weeks", 0),
        "new_badges": [b for b in new_badges if b not in (user.get("challenge_badges") or [])],
    }

@api_router.get("/challenges/leaderboard")
async def challenge_leaderboard(user: dict = Depends(get_current_user)):
    """Top 10 users by XP. Returns minimal public profile info."""
    top = await db.users.find(
        {"xp": {"$gt": 0}},
        {"_id": 0, "id": 1, "name": 1, "photos": 1, "xp": 1, "streak_weeks": 1, "challenge_badges": 1}
    ).sort("xp", -1).limit(10).to_list(10)
    me_rank = None
    if user.get("xp", 0) > 0:
        better = await db.users.count_documents({"xp": {"$gt": user.get("xp", 0)}})
        me_rank = better + 1
    return {
        "leaderboard": [
            {
                "id": u["id"],
                "name": u.get("name", "Anonymous"),
                "photo": (u.get("photos") or [None])[0],
                "xp": u.get("xp", 0),
                "streak_weeks": u.get("streak_weeks", 0),
                "badges_count": len(u.get("challenge_badges") or []),
            }
            for u in top
        ],
        "my_rank": me_rank,
        "my_xp": user.get("xp", 0),
    }

@api_router.get("/challenges/history")
async def challenge_history(user: dict = Depends(get_current_user)):
    """User's completed challenges history (last 50)."""
    items = await db.challenge_completions.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("completed_at", -1).limit(50).to_list(50)
    # Attach challenge titles
    by_id = {c["id"]: c for c in WEEKLY_CHALLENGES}
    for i in items:
        c = by_id.get(i.get("challenge_id"))
        if c:
            i["title"] = c["title"]
            i["icon"] = c.get("verb", "spark")
    return {"completions": items}

# ==================== PUSH NOTIFICATIONS (WEB PUSH) ====================

from pywebpush import webpush, WebPushException
import requests as _requests

VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_CLAIM_EMAIL = os.environ.get("VAPID_CLAIM_EMAIL", "mailto:support@sparkmatch.dating")

class PushSubscriptionPayload(BaseModel):
    endpoint: str
    keys: Dict[str, str]  # {p256dh, auth}
    user_agent: Optional[str] = None

@api_router.get("/push/vapid-public-key")
async def get_vapid_public_key():
    """Frontend needs this to subscribe via PushManager.subscribe."""
    return {"public_key": VAPID_PUBLIC_KEY}

@api_router.post("/push/subscribe")
async def push_subscribe(payload: PushSubscriptionPayload, user: dict = Depends(get_current_user)):
    """Register a browser push subscription for the current user."""
    record = {
        "user_id": user["id"],
        "endpoint": payload.endpoint,
        "keys": payload.keys,
        "user_agent": payload.user_agent,
        "subscribed_at": datetime.now(timezone.utc).isoformat(),
        "active": True,
    }
    await db.push_subscriptions.update_one(
        {"user_id": user["id"], "endpoint": payload.endpoint},
        {"$set": record},
        upsert=True,
    )
    return {"subscribed": True}

@api_router.post("/push/unsubscribe")
async def push_unsubscribe(payload: dict, user: dict = Depends(get_current_user)):
    endpoint = payload.get("endpoint")
    if not endpoint:
        raise HTTPException(status_code=400, detail="endpoint required")
    await db.push_subscriptions.delete_one({"user_id": user["id"], "endpoint": endpoint})
    return {"unsubscribed": True}

async def push_notify_user(user_id: str, title: str, body: str, url: str = "/discover", tag: Optional[str] = None) -> int:
    """Send a web-push to every active subscription of a user. Returns count sent."""
    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        logger.warning("VAPID keys not configured; push skipped")
        return 0
    subs = await db.push_subscriptions.find({"user_id": user_id, "active": True}).to_list(20)
    if not subs:
        return 0
    payload = json.dumps({"title": title, "body": body, "url": url, "tag": tag or "spark"})
    sent = 0
    for s in subs:
        sub_info = {"endpoint": s["endpoint"], "keys": s["keys"]}
        try:
            await asyncio.to_thread(
                webpush,
                subscription_info=sub_info,
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_CLAIM_EMAIL},
            )
            sent += 1
        except WebPushException as e:
            # 410 Gone → subscription removed/expired
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (404, 410):
                await db.push_subscriptions.update_one(
                    {"_id": s["_id"]},
                    {"$set": {"active": False, "deactivated_at": datetime.now(timezone.utc).isoformat()}}
                )
                logger.info(f"Deactivated stale subscription for user {user_id}")
            else:
                logger.error(f"Push failed for user {user_id}: {e}")
        except Exception as e:
            logger.error(f"Push unexpected error: {e}")
    return sent

@api_router.post("/push/test")
async def push_test(user: dict = Depends(get_current_user)):
    """Send a test push to the current user. Useful for verifying setup."""
    n = await push_notify_user(user["id"], "It works! ⚡", "Push notifications are live on this device.", url="/profile", tag="push-test")
    return {"sent": n}

# ==================== EMERGENT OBJECT STORAGE (PHOTO UPLOADS) ====================

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
APP_NAME = "spark-dating"
_storage_key_cache = {"key": None, "set_at": None}

def init_storage(force: bool = False) -> Optional[str]:
    """Call lazily. Returns a session-scoped, reusable storage_key. None on failure (caller decides)."""
    if not force and _storage_key_cache["key"]:
        return _storage_key_cache["key"]
    if not EMERGENT_LLM_KEY:
        logger.error("EMERGENT_LLM_KEY missing — storage init aborted")
        return None
    try:
        resp = _requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_LLM_KEY}, timeout=30)
        resp.raise_for_status()
        key = resp.json().get("storage_key")
        _storage_key_cache["key"] = key
        _storage_key_cache["set_at"] = datetime.now(timezone.utc).isoformat()
        logger.info("Emergent object storage initialized")
        return key
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
        return None

def put_object_sync(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    if not key:
        raise HTTPException(status_code=503, detail="Storage unavailable")
    resp = _requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    if resp.status_code in (401, 403):
        # Refresh and retry once
        init_storage(force=True)
        key = _storage_key_cache["key"]
        resp = _requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data,
            timeout=120,
        )
    resp.raise_for_status()
    return resp.json()

def get_object_sync(path: str) -> tuple:
    key = init_storage()
    if not key:
        raise HTTPException(status_code=503, detail="Storage unavailable")
    resp = _requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key},
        timeout=60,
    )
    if resp.status_code in (401, 403):
        init_storage(force=True)
        key = _storage_key_cache["key"]
        resp = _requests.get(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key},
            timeout=60,
        )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5MB

@api_router.post("/profile/photo/upload")
async def upload_photo(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Upload a profile photo to Emergent Object Storage and append URL to user.photos[]."""
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {content_type}. Use JPEG/PNG/WebP.")
    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_PHOTO_BYTES // (1024*1024)}MB)")
    ext = "jpg" if content_type == "image/jpeg" else ("png" if content_type == "image/png" else "webp")
    path = f"{APP_NAME}/photos/{user['id']}/{uuid.uuid4()}.{ext}"
    try:
        result = await asyncio.to_thread(put_object_sync, path, data, content_type)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Photo upload failed: {e}")
        raise HTTPException(status_code=502, detail="Upload failed, please retry")
    file_id = str(uuid.uuid4())
    record = {
        "id": file_id,
        "user_id": user["id"],
        "storage_path": result.get("path", path),
        "original_filename": file.filename,
        "content_type": content_type,
        "size": result.get("size", len(data)),
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.files.insert_one(record)
    # Build public URL — served via our /api/files/{path:path} route
    backend_origin = os.environ.get("BACKEND_PUBLIC_URL", "")
    public_url = f"/api/files/{record['storage_path']}"
    # Append to user's photos[] (front-of-list if no photos yet, otherwise end)
    photos = list(user.get("photos") or [])
    photos.append(public_url)
    await db.users.update_one({"id": user["id"]}, {"$set": {"photos": photos}})
    return {"file_id": file_id, "url": public_url, "size": record["size"], "photos": photos}

@api_router.delete("/profile/photo")
async def delete_photo(payload: dict, user: dict = Depends(get_current_user)):
    """Soft-delete: remove URL from user.photos[] (does not purge from object storage)."""
    url = (payload or {}).get("url")
    if not url:
        raise HTTPException(status_code=400, detail="url required")
    photos = [p for p in (user.get("photos") or []) if p != url]
    await db.users.update_one({"id": user["id"]}, {"$set": {"photos": photos}})
    # Mark file record deleted (best-effort)
    if url.startswith("/api/files/"):
        storage_path = url[len("/api/files/"):]
        await db.files.update_many({"storage_path": storage_path, "user_id": user["id"]}, {"$set": {"is_deleted": True}})
    return {"photos": photos}

from fastapi import Response, Header, Query
from fastapi.responses import Response as FastAPIResponse

@api_router.get("/files/{path:path}")
async def download_file(path: str, authorization: Optional[str] = Header(None), auth: Optional[str] = Query(None)):
    """Serve uploaded files. Accepts auth via Authorization header OR ?auth= query (for <img src>)."""
    auth_header = authorization or (f"Bearer {auth}" if auth else None)
    # Photos are public to authenticated users (matches social-graph privacy of profile photos)
    if auth_header:
        try:
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth_header.replace("Bearer ", ""))
            await get_current_user(credentials)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")
    else:
        # Allow unauthenticated GET for now to keep <img> tags simple; can tighten later
        pass
    record = await db.files.find_one({"storage_path": path, "is_deleted": False})
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        data, content_type = await asyncio.to_thread(get_object_sync, path)
    except Exception as e:
        logger.error(f"File download failed: {e}")
        raise HTTPException(status_code=502, detail="Download failed")
    return FastAPIResponse(content=data, media_type=record.get("content_type") or content_type)

# ==================== BACKGROUND SCHEDULER (CRON) ====================

from apscheduler.schedulers.asyncio import AsyncIOScheduler
scheduler = AsyncIOScheduler(timezone="UTC")

async def _scheduled_sweep():
    """Runs every 5 minutes: sweep overdue post-date check-ins for ALL users."""
    try:
        res = await _sweep_post_date_alerts()
        if res.get("alerted", 0) > 0:
            logger.info(f"Scheduled sweep: alerted={res['alerted']} pushed={res.get('pushed', 0)}")
    except Exception as e:
        logger.error(f"Scheduled sweep error: {e}")

async def _scheduled_new_week():
    """Runs every Monday 09:00 UTC: push a fresh Weekly Spark Challenge nudge to all active users."""
    try:
        challenge = _active_challenge()
        week_key = _current_week_key()
        # Push to users who logged in within the last 30 days
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        users = await db.users.find({"last_active": {"$gte": cutoff}}, {"_id": 0, "id": 1}).limit(5000).to_list(5000)
        pushed = 0
        for u in users:
            try:
                n = await push_notify_user(u["id"], "New Spark Challenge!", f"This week: {challenge['title']} (+{challenge['xp']} XP)", url="/challenges", tag=f"weekly-{week_key}")
                pushed += n
            except Exception:
                continue
        logger.info(f"Monday push delivered to {pushed} subscriptions for {week_key}")
    except Exception as e:
        logger.error(f"Monday push error: {e}")

@app.on_event("startup")
async def _on_startup():
    # Initialize object storage (non-blocking on failure)
    try:
        await asyncio.to_thread(init_storage)
    except Exception as e:
        logger.warning(f"Storage init at startup failed: {e}")
    # TTL index for live location shares — Mongo auto-purges expired docs every ~60s
    try:
        await db.location_shares.create_index("expires_at", expireAfterSeconds=0, name="ttl_expires_at")
        # Clean up any leftover docs with ISO-string expires_at from before BSON datetime migration
        legacy = await db.location_shares.find({"expires_at": {"$type": "string"}}, {"_id": 1}).to_list(500)
        if legacy:
            await db.location_shares.delete_many({"_id": {"$in": [d["_id"] for d in legacy]}})
            logger.info(f"Purged {len(legacy)} legacy ISO-string location_shares (pre-TTL)")
        logger.info("TTL index on location_shares.expires_at ready")
    except Exception as e:
        logger.warning(f"TTL index init failed: {e}")
    # Start scheduler
    if not scheduler.running:
        scheduler.add_job(_scheduled_sweep, "interval", minutes=5, id="post_date_sweep", replace_existing=True, max_instances=1)
        scheduler.add_job(_scheduled_new_week, "cron", day_of_week="mon", hour=9, minute=0, id="weekly_challenge_push", replace_existing=True)
        scheduler.start()
        logger.info("Scheduler started: post_date_sweep (5min), weekly_challenge_push (Mon 09:00 UTC)")

# ==================== AUTO-PUSH HOOKS ====================
# Background helpers that other endpoints (match created, message sent) call to fire pushes.

async def push_on_new_match(user_id: str, match_id: str, other_name: str):
    """Fire push to one side of a new match."""
    await push_notify_user(user_id, "It's a match! ⚡", f"You and {other_name} are now matched. Send the first message?", url=f"/chat/{match_id}", tag=f"match-{match_id}")

async def push_on_new_message(receiver_id: str, sender_name: str, match_id: str, preview: str):
    """Fire push for a new chat message (only if receiver is offline / not in chat)."""
    snippet = (preview or "")[:80]
    await push_notify_user(receiver_id, f"{sender_name}", snippet or "New message", url=f"/chat/{match_id}", tag=f"msg-{match_id}")

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
