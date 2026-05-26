"""Iteration 4 backend tests for Spark dating app:
- Resend email (placeholder key — graceful failure)
- Profile Boost (POST/GET /api/me/boost, /status)
- Profile Viewers (POST /api/profile/view/{id}, GET /api/me/viewers)
- Undo Swipe (POST /api/swipe/undo)
- Discover regression (is_boosted field, boosted-first sort)
"""
import os
import time
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

DEMO1 = {"email": "demo1@spark.app", "password": "password123"}
DEMO2 = {"email": "demo2@spark.app", "password": "password123"}
ADMIN = {"email": "deepthimarthi82@gmail.com", "password": "Spark2026!"}


@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login fail {email}: {r.status_code} {r.text[:200]}")
    return r.json()


def _auth(email, password):
    d = _login(email, password)
    return {"user_id": d["user_id"], "headers": {"Authorization": f"Bearer {d['token']}"}}


@pytest.fixture(scope="module")
def demo1():
    return _auth(**DEMO1)


@pytest.fixture(scope="module")
def demo2():
    return _auth(**DEMO2)


@pytest.fixture(scope="module")
def admin():
    return _auth(**ADMIN)


@pytest.fixture(autouse=True)
def reset_admin_boost_events(db, admin):
    """Clean boost_events + boost_active_until for admin before each test, so tests are independent."""
    db.boost_events.delete_many({"user_id": admin["user_id"]})
    db.users.update_one({"id": admin["user_id"]}, {"$unset": {"boost_active_until": ""}})
    yield


# ==================== Support (Resend graceful failure) ====================
class TestSupportEmailGracefulFailure:
    def test_support_contact_saves_ticket_no_error(self, demo1, db):
        payload = {
            "name": "TEST iter4",
            "email": "demo1@spark.app",
            "issue_type": "general",
            "message": "TEST iter4 contact — resend placeholder",
            "urgent": False,
        }
        r = requests.post(f"{BASE_URL}/api/support/contact", json=payload, headers=demo1["headers"], timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "ticket_id" in data
        # Verify persisted with deliver_to
        rec = db.support_tickets.find_one({"id": data["ticket_id"]})
        assert rec is not None
        assert rec["deliver_to"] == "support@sparkmatch.dating"
        assert rec["message"] == payload["message"]

    def test_bug_report_saves_no_error(self, demo1, db):
        payload = {"description": "TEST iter4 bug-report", "page_url": "/discover", "browser": "pytest"}
        r = requests.post(f"{BASE_URL}/api/support/bug-report", json=payload, headers=demo1["headers"], timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "report_id" in data
        rec = db.bug_reports.find_one({"id": data["report_id"]})
        assert rec is not None
        assert rec["deliver_to"] == "support@sparkmatch.dating"


# ==================== Profile Boost ====================
class TestProfileBoost:
    def test_boost_free_returns_402(self, demo1):
        r = requests.post(f"{BASE_URL}/api/me/boost", headers=demo1["headers"], timeout=30)
        assert r.status_code == 402, r.text
        body = r.json()
        # FastAPI HTTPException nests under "detail"
        detail = body.get("detail", body)
        assert detail.get("premium_required") is True

    def test_boost_vip_success(self, admin):
        r = requests.post(f"{BASE_URL}/api/me/boost", headers=admin["headers"], timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "boost_active_until" in data
        assert data["boosts_remaining_this_week"] == 2  # 3 limit - 1 used

    def test_boost_status_vip_active(self, admin):
        # Activate boost first
        requests.post(f"{BASE_URL}/api/me/boost", headers=admin["headers"], timeout=30)
        r = requests.get(f"{BASE_URL}/api/me/boost/status", headers=admin["headers"], timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["weekly_limit"] == 3
        assert data["is_active"] is True
        assert data["active_until"] is not None
        assert data["boosts_remaining_this_week"] == 2

    def test_boost_status_free(self, demo1):
        r = requests.get(f"{BASE_URL}/api/me/boost/status", headers=demo1["headers"], timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["weekly_limit"] == 0
        assert data["is_active"] is False

    def test_boost_vip_4th_call_429(self, admin):
        # Call 4x
        r1 = requests.post(f"{BASE_URL}/api/me/boost", headers=admin["headers"], timeout=30)
        r2 = requests.post(f"{BASE_URL}/api/me/boost", headers=admin["headers"], timeout=30)
        r3 = requests.post(f"{BASE_URL}/api/me/boost", headers=admin["headers"], timeout=30)
        r4 = requests.post(f"{BASE_URL}/api/me/boost", headers=admin["headers"], timeout=30)
        assert r1.status_code == 200, r1.text
        assert r2.status_code == 200, r2.text
        assert r3.status_code == 200, r3.text
        assert r4.status_code == 429, r4.text
        body = r4.json()
        msg = str(body.get("detail", body))
        assert "3" in msg and ("boost" in msg.lower() or "used" in msg.lower())


# ==================== Profile Viewers ====================
class TestProfileViewers:
    def test_view_self_not_recorded(self, demo1):
        r = requests.post(f"{BASE_URL}/api/profile/view/{demo1['user_id']}", headers=demo1["headers"], timeout=30)
        assert r.status_code == 200, r.text
        assert r.json() == {"recorded": False}

    def test_view_target_idempotent(self, db, demo1, demo2):
        # Clean previous views from demo1 to demo2 in last hour
        db.profile_views.delete_many({"viewer_id": demo1["user_id"], "viewed_id": demo2["user_id"]})
        r1 = requests.post(f"{BASE_URL}/api/profile/view/{demo2['user_id']}", headers=demo1["headers"], timeout=30)
        assert r1.status_code == 200, r1.text
        assert r1.json().get("recorded") is True
        r2 = requests.post(f"{BASE_URL}/api/profile/view/{demo2['user_id']}", headers=demo1["headers"], timeout=30)
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        assert body2.get("recorded") is False
        assert body2.get("deduped") is True

    def test_viewers_free_returns_402(self, demo1):
        r = requests.get(f"{BASE_URL}/api/me/viewers", headers=demo1["headers"], timeout=30)
        assert r.status_code == 402, r.text
        detail = r.json().get("detail", {})
        assert detail.get("premium_required") is True

    def test_viewers_vip_returns_list_no_user_not_found(self, db, demo1, admin):
        # Setup: demo1 viewed admin recently
        db.profile_views.delete_many({"viewer_id": demo1["user_id"], "viewed_id": admin["user_id"]})
        r0 = requests.post(f"{BASE_URL}/api/profile/view/{admin['user_id']}", headers=demo1["headers"], timeout=30)
        assert r0.status_code == 200, r0.text

        r = requests.get(f"{BASE_URL}/api/me/viewers", headers=admin["headers"], timeout=30)
        # Critical: should NOT be 404 "User not found"
        assert r.status_code == 200, r.text
        data = r.json()
        assert "viewers" in data
        assert "total" in data
        assert isinstance(data["viewers"], list)
        # demo1 should appear with required fields
        demo1_viewer = next((v for v in data["viewers"] if v["id"] == demo1["user_id"]), None)
        assert demo1_viewer is not None, f"demo1 not in viewers: {data}"
        assert "name" in demo1_viewer
        assert "view_count" in demo1_viewer
        assert demo1_viewer["view_count"] >= 1
        assert "last_viewed_at" in demo1_viewer


# ==================== Undo Swipe ====================
class TestUndoSwipe:
    def test_undo_free_returns_402(self, demo1):
        r = requests.post(f"{BASE_URL}/api/swipe/undo", headers=demo1["headers"], timeout=30)
        assert r.status_code == 402, r.text
        detail = r.json().get("detail", {})
        assert detail.get("premium_required") is True

    def test_undo_premium_success(self, db, demo1, demo2):
        # Snapshot original demo1 subscription
        orig = db.users.find_one({"id": demo1["user_id"]})
        orig_sub = orig.get("subscription", "free")
        orig_swipes = orig.get("daily_swipes_remaining", 20)
        try:
            # Promote demo1 to premium
            db.users.update_one({"id": demo1["user_id"]}, {"$set": {"subscription": "premium"}})

            # Create a fresh target user to swipe so we don't pollute existing demo1<->demo2 match
            # Use a registered new user
            import uuid as _uuid
            new_email = f"iter4_target_{_uuid.uuid4().hex[:8]}@example.com"
            reg = requests.post(f"{BASE_URL}/api/auth/register", json={
                "email": new_email, "password": "password123", "name": "Iter4 Target",
                "age": 27, "gender": "man", "looking_for": "everyone"
            }, timeout=30)
            assert reg.status_code in (200, 201), reg.text
            target_id = reg.json()["user_id"]

            # Make profile_complete so they appear in discover (not required for direct swipe though)
            db.users.update_one({"id": target_id}, {"$set": {"profile_complete": True}})

            # Clear any existing swipe records demo1->target
            db.swipes.delete_many({"swiper_id": demo1["user_id"], "swiped_id": target_id})
            db.matches.delete_many({"$or": [
                {"user1_id": demo1["user_id"], "user2_id": target_id},
                {"user1_id": target_id, "user2_id": demo1["user_id"]}
            ]})

            # Swipe like
            sw = requests.post(f"{BASE_URL}/api/swipe", json={"target_user_id": target_id, "action": "like"},
                               headers=demo1["headers"], timeout=30)
            assert sw.status_code == 200, sw.text
            # Verify swipe row exists
            assert db.swipes.find_one({"swiper_id": demo1["user_id"], "swiped_id": target_id}) is not None

            # Undo
            un = requests.post(f"{BASE_URL}/api/swipe/undo", headers=demo1["headers"], timeout=30)
            assert un.status_code == 200, un.text
            body = un.json()
            assert "undone" in body and "action" in body
            assert body["undone"] == target_id
            assert body["action"] == "like"
            # Verify swipe row removed
            assert db.swipes.find_one({"swiper_id": demo1["user_id"], "swiped_id": target_id}) is None

            # Cleanup target user
            db.users.delete_one({"id": target_id})
        finally:
            # Restore demo1 subscription
            db.users.update_one(
                {"id": demo1["user_id"]},
                {"$set": {"subscription": orig_sub, "daily_swipes_remaining": orig_swipes}}
            )

    def test_undo_premium_match_cleanup(self, db, demo1):
        """When undo removes a swipe that created a match, the match must be deleted too."""
        orig = db.users.find_one({"id": demo1["user_id"]})
        orig_sub = orig.get("subscription", "free")
        try:
            db.users.update_one({"id": demo1["user_id"]}, {"$set": {"subscription": "premium"}})

            import uuid as _uuid
            new_email = f"iter4_match_{_uuid.uuid4().hex[:8]}@example.com"
            reg = requests.post(f"{BASE_URL}/api/auth/register", json={
                "email": new_email, "password": "password123", "name": "Iter4 Match",
                "age": 27, "gender": "man", "looking_for": "everyone"
            }, timeout=30)
            assert reg.status_code in (200, 201), reg.text
            target_id = reg.json()["user_id"]
            target_token = reg.json()["token"]
            target_headers = {"Authorization": f"Bearer {target_token}"}
            db.users.update_one({"id": target_id}, {"$set": {"profile_complete": True}})

            # Target likes demo1 first
            r1 = requests.post(f"{BASE_URL}/api/swipe",
                               json={"target_user_id": demo1["user_id"], "action": "like"},
                               headers=target_headers, timeout=30)
            assert r1.status_code == 200, r1.text

            # demo1 likes target -> creates match
            r2 = requests.post(f"{BASE_URL}/api/swipe",
                               json={"target_user_id": target_id, "action": "like"},
                               headers=demo1["headers"], timeout=30)
            assert r2.status_code == 200, r2.text
            assert r2.json().get("is_match") is True

            # Verify match created
            match = db.matches.find_one({"$or": [
                {"user1_id": demo1["user_id"], "user2_id": target_id},
                {"user1_id": target_id, "user2_id": demo1["user_id"]}
            ]})
            assert match is not None

            # Undo
            un = requests.post(f"{BASE_URL}/api/swipe/undo", headers=demo1["headers"], timeout=30)
            assert un.status_code == 200, un.text

            # Match should be gone
            match_after = db.matches.find_one({"$or": [
                {"user1_id": demo1["user_id"], "user2_id": target_id},
                {"user1_id": target_id, "user2_id": demo1["user_id"]}
            ]})
            assert match_after is None, "Match was not cleaned up on undo"

            # Cleanup
            db.swipes.delete_many({"$or": [
                {"swiper_id": demo1["user_id"], "swiped_id": target_id},
                {"swiper_id": target_id, "swiped_id": demo1["user_id"]}
            ]})
            db.users.delete_one({"id": target_id})
        finally:
            db.users.update_one({"id": demo1["user_id"]}, {"$set": {"subscription": orig_sub}})


# ==================== Discover regression ====================
class TestDiscoverBoosted:
    def test_discover_has_is_boosted_field(self, demo1):
        r = requests.get(f"{BASE_URL}/api/discover", headers=demo1["headers"], timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "profiles" in data
        if data["profiles"]:
            for p in data["profiles"]:
                assert "is_boosted" in p
                assert isinstance(p["is_boosted"], bool)

    def test_discover_boosted_profiles_appear_first(self, db, demo1):
        """Create a fresh male candidate, mark them boosted, ensure they're first in demo1's discover."""
        from datetime import datetime, timezone, timedelta
        import uuid as _uuid
        # Register a new male candidate that demo1 (woman -> men) would see
        email = f"iter4_boost_{_uuid.uuid4().hex[:8]}@example.com"
        reg = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email, "password": "password123", "name": "Boosted Bob",
            "age": 28, "gender": "man", "looking_for": "women"
        }, timeout=30)
        assert reg.status_code in (200, 201), reg.text
        cand_id = reg.json()["user_id"]
        try:
            future = (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat()
            db.users.update_one({"id": cand_id}, {"$set": {
                "boost_active_until": future,
                "profile_complete": True,
                "gender": "man",
                "photos": ["https://example.com/x.jpg"],
            }})
            # Ensure demo1 hasn't swiped them
            db.swipes.delete_many({"swiper_id": demo1["user_id"], "swiped_id": cand_id})

            r = requests.get(f"{BASE_URL}/api/discover", headers=demo1["headers"], timeout=30)
            assert r.status_code == 200, r.text
            profiles = r.json().get("profiles", [])
            if not profiles:
                pytest.skip("No profiles in demo1's discover")

            cand_profile = next((p for p in profiles if p["id"] == cand_id), None)
            assert cand_profile is not None, "Boosted candidate not in discover pool"
            assert cand_profile["is_boosted"] is True
            # Boosted candidate must be at position 0
            assert profiles[0]["id"] == cand_id, f"First profile is {profiles[0]['id']}, expected boosted {cand_id}"
            assert profiles[0]["is_boosted"] is True
        finally:
            db.users.delete_one({"id": cand_id})
            db.swipes.delete_many({"swiper_id": demo1["user_id"], "swiped_id": cand_id})


# ==================== Route collision regression ====================
class TestMeViewersNoUserNotFoundCollision:
    def test_me_viewers_not_treated_as_profile_id(self, demo1, admin):
        """Ensures GET /api/me/viewers route is matched BEFORE /api/profile/{user_id}."""
        # Free user gets 402 not 404
        r_free = requests.get(f"{BASE_URL}/api/me/viewers", headers=demo1["headers"], timeout=30)
        assert r_free.status_code == 402, f"Got {r_free.status_code}: {r_free.text}"
        # VIP gets 200, definitely not 'User not found'
        r_vip = requests.get(f"{BASE_URL}/api/me/viewers", headers=admin["headers"], timeout=30)
        assert r_vip.status_code == 200, r_vip.text
        assert "viewers" in r_vip.json()
