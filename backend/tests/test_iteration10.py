"""Iteration 10 — TTL index on location_shares + profile activity status (last_active / is_online)."""
import os
import time
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://spark-dating-118.preview.emergentagent.com").rstrip("/")
if not BASE_URL or "localhost" in BASE_URL:
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
    except Exception:
        pass

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"
try:
    with open("/app/backend/.env") as f:
        for line in f:
            if line.startswith("MONGO_URL="):
                MONGO_URL = line.split("=", 1)[1].strip().strip('"')
            if line.startswith("DB_NAME="):
                DB_NAME = line.split("=", 1)[1].strip().strip('"')
except Exception:
    pass

DEMO1 = {"email": "demo1@spark.app", "password": "password123"}
DEMO2 = {"email": "demo2@spark.app", "password": "password123"}


@pytest.fixture(scope="module")
def mongo_db():
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Cannot login {email}: {r.status_code} {r.text[:200]}")
    return r.json()


@pytest.fixture(scope="module")
def demo1_auth():
    d = _login(**DEMO1)
    return {"token": d["token"], "user_id": d["user_id"], "headers": {"Authorization": f"Bearer {d['token']}"}}


@pytest.fixture(scope="module")
def demo2_auth():
    d = _login(**DEMO2)
    return {"token": d["token"], "user_id": d["user_id"], "headers": {"Authorization": f"Bearer {d['token']}"}}


@pytest.fixture(scope="module")
def match_id(demo1_auth, demo2_auth):
    r = requests.get(f"{BASE_URL}/api/matches", headers=demo1_auth["headers"], timeout=30)
    assert r.status_code == 200, r.text
    for m in r.json().get("matches", []):
        if m["user"]["id"] == demo2_auth["user_id"]:
            return m["match_id"]
    pytest.skip("No demo1↔demo2 match")


# ==================== TTL INDEX ====================

class TestTTLIndex:
    """Verify TTL index on location_shares.expires_at."""

    def test_ttl_index_exists(self, mongo_db):
        idxs = list(mongo_db.location_shares.list_indexes())
        ttl_idx = None
        for i in idxs:
            if i.get("name") == "ttl_expires_at":
                ttl_idx = i
                break
        assert ttl_idx is not None, f"ttl_expires_at index not found. Got: {[i.get('name') for i in idxs]}"
        # expireAfterSeconds=0
        assert ttl_idx.get("expireAfterSeconds") == 0, f"Wrong expireAfterSeconds: {ttl_idx.get('expireAfterSeconds')}"
        # Key on expires_at
        key = ttl_idx.get("key")
        assert "expires_at" in dict(key), f"Index key wrong: {key}"

    def test_share_location_stores_bson_datetime(self, demo1_auth, match_id, mongo_db):
        payload = {
            "match_id": match_id,
            "latitude": 12.34,
            "longitude": 56.78,
            "duration_minutes": 15,
        }
        r = requests.post(f"{BASE_URL}/api/safety/share-location", json=payload, headers=demo1_auth["headers"], timeout=30)
        assert r.status_code == 200, r.text
        assert r.json().get("shared") is True
        try:
            doc = mongo_db.location_shares.find_one({"user_id": demo1_auth["user_id"], "match_id": match_id})
            assert doc is not None
            exp = doc.get("expires_at")
            # Must be a datetime, not str
            assert isinstance(exp, datetime), f"expires_at should be datetime BSON, got {type(exp).__name__}: {exp}"
            # Should be ~15 minutes in the future
            now = datetime.now(timezone.utc)
            exp_aware = exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
            delta_min = (exp_aware - now).total_seconds() / 60
            assert 10 < delta_min < 20, f"expires_at not ~15 min in future: {delta_min}min"
        finally:
            requests.delete(f"{BASE_URL}/api/safety/share-location/{match_id}", headers=demo1_auth["headers"], timeout=30)

    def test_expired_share_returns_expired_true(self, demo1_auth, demo2_auth, match_id, mongo_db):
        """Manually insert a doc with past expiry → GET should return {sharing:false, expired:true}."""
        # Insert directly so other_user (demo2 sharing TO demo1) has an expired share
        past = datetime.now(timezone.utc) - timedelta(minutes=5)
        mongo_db.location_shares.update_one(
            {"user_id": demo2_auth["user_id"], "match_id": match_id},
            {"$set": {
                "user_id": demo2_auth["user_id"],
                "match_id": match_id,
                "latitude": 1.0,
                "longitude": 2.0,
                "expires_at": past,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True
        )
        try:
            r = requests.get(f"{BASE_URL}/api/safety/share-location/{match_id}", headers=demo1_auth["headers"], timeout=30)
            assert r.status_code == 200, r.text
            data = r.json()
            # Either expired+false (if TTL hasn't run yet) OR no doc at all (if TTL purged)
            assert data.get("sharing") is False, f"Expected sharing=false, got {data}"
            # If doc still exists, expired flag must be true
            doc = mongo_db.location_shares.find_one({"user_id": demo2_auth["user_id"], "match_id": match_id})
            if doc is not None:
                assert data.get("expired") is True, f"Doc still in DB but no expired flag: {data}"
        finally:
            mongo_db.location_shares.delete_many({"user_id": demo2_auth["user_id"], "match_id": match_id})

    def test_legacy_iso_string_expires_at_does_not_crash(self, demo1_auth, demo2_auth, match_id, mongo_db):
        """Backwards-compat: legacy ISO-string expires_at should still work in GET."""
        past_iso = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        mongo_db.location_shares.update_one(
            {"user_id": demo2_auth["user_id"], "match_id": match_id},
            {"$set": {
                "user_id": demo2_auth["user_id"],
                "match_id": match_id,
                "latitude": 3.0,
                "longitude": 4.0,
                "expires_at": past_iso,  # legacy ISO string
                "updated_at": past_iso,
            }},
            upsert=True
        )
        try:
            r = requests.get(f"{BASE_URL}/api/safety/share-location/{match_id}", headers=demo1_auth["headers"], timeout=30)
            assert r.status_code == 200, f"GET crashed on legacy ISO doc: {r.status_code} {r.text}"
            data = r.json()
            assert data.get("sharing") is False
            assert data.get("expired") is True
        finally:
            mongo_db.location_shares.delete_many({"user_id": demo2_auth["user_id"], "match_id": match_id})


# ==================== ACTIVITY STATUS ====================

class TestActivityStatus:
    """last_active_human + is_online in /api/profile/{id}, /api/discover, /api/matches."""

    def test_profile_endpoint_has_last_active_fields(self, demo1_auth, demo2_auth):
        r = requests.get(f"{BASE_URL}/api/profile/{demo2_auth['user_id']}", headers=demo1_auth["headers"], timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "last_active_human" in data, f"Missing last_active_human. Keys: {list(data.keys())}"
        assert "is_online" in data
        assert isinstance(data["last_active_human"], str)
        assert isinstance(data["is_online"], bool)

    def test_discover_profiles_have_last_active_fields(self, demo1_auth):
        r = requests.get(f"{BASE_URL}/api/discover", headers=demo1_auth["headers"], timeout=30)
        assert r.status_code == 200, r.text
        # discover may return {profiles:[...]} or list
        body = r.json()
        profiles = body.get("profiles") if isinstance(body, dict) else body
        if not profiles:
            pytest.skip("No discover profiles available")
        for p in profiles[:3]:
            assert "last_active_human" in p, f"Discover profile missing last_active_human: keys={list(p.keys())}"
            assert "is_online" in p
            assert isinstance(p["is_online"], bool)

    def test_matches_user_has_last_active_fields(self, demo1_auth, demo2_auth):
        r = requests.get(f"{BASE_URL}/api/matches", headers=demo1_auth["headers"], timeout=30)
        assert r.status_code == 200
        matches = r.json().get("matches", [])
        if not matches:
            pytest.skip("No matches")
        for m in matches:
            user = m.get("user", {})
            assert "last_active_human" in user, f"match.user missing last_active_human: {list(user.keys())}"
            assert "is_online" in user
            assert isinstance(user["is_online"], bool)


# ==================== LAST_ACTIVE THROTTLE ====================

class TestLastActiveThrottle:
    """Rapid auth calls should only bump last_active once per 60s."""

    def test_rapid_calls_do_not_move_timestamp(self, demo1_auth, mongo_db):
        # Snapshot original
        original = mongo_db.users.find_one({"id": demo1_auth["user_id"]}, {"last_active": 1})
        original_la = original.get("last_active") if original else None
        try:
            # First call - may update if last update was >60s ago
            requests.get(f"{BASE_URL}/api/auth/me", headers=demo1_auth["headers"], timeout=30)
            # tiny delay to ensure async write completes
            time.sleep(1.5)
            after_first = mongo_db.users.find_one({"id": demo1_auth["user_id"]}, {"last_active": 1})["last_active"]
            # Now 4 more rapid calls
            for _ in range(4):
                requests.get(f"{BASE_URL}/api/auth/me", headers=demo1_auth["headers"], timeout=30)
            time.sleep(1.5)
            after_rapid = mongo_db.users.find_one({"id": demo1_auth["user_id"]}, {"last_active": 1})["last_active"]
            # last_active must NOT have moved during the rapid burst (throttle window=60s)
            assert after_first == after_rapid, f"last_active moved during throttle window: {after_first} → {after_rapid}"
        finally:
            # Restore original (best-effort; not strictly necessary as throttle is benign)
            if original_la is not None:
                mongo_db.users.update_one({"id": demo1_auth["user_id"]}, {"$set": {"last_active": original_la}})


# ==================== HUMAN_LAST_ACTIVE EDGE CASES ====================

class TestHumanLastActive:
    """Set last_active to specific past times, verify the human text on /api/profile/{id}."""

    @pytest.fixture(autouse=True)
    def _snapshot_demo2(self, demo2_auth, mongo_db):
        # Snapshot demo2's last_active so we can restore
        u = mongo_db.users.find_one({"id": demo2_auth["user_id"]}, {"last_active": 1})
        self._original = u.get("last_active") if u else None
        yield
        if self._original is not None:
            mongo_db.users.update_one({"id": demo2_auth["user_id"]}, {"$set": {"last_active": self._original}})

    def _set_la_and_get(self, demo1_auth, demo2_auth, mongo_db, when: datetime) -> str:
        mongo_db.users.update_one(
            {"id": demo2_auth["user_id"]},
            {"$set": {"last_active": when.isoformat()}}
        )
        r = requests.get(f"{BASE_URL}/api/profile/{demo2_auth['user_id']}", headers=demo1_auth["headers"], timeout=30)
        assert r.status_code == 200
        return r.json().get("last_active_human", "")

    def test_active_now(self, demo1_auth, demo2_auth, mongo_db):
        # 60s ago → secs<300 → "Active now"
        when = datetime.now(timezone.utc) - timedelta(seconds=60)
        text = self._set_la_and_get(demo1_auth, demo2_auth, mongo_db, when)
        assert text == "Active now", text

    def test_minutes_ago(self, demo1_auth, demo2_auth, mongo_db):
        # 12 minutes ago → "Active 12m ago"
        when = datetime.now(timezone.utc) - timedelta(minutes=12)
        text = self._set_la_and_get(demo1_auth, demo2_auth, mongo_db, when)
        assert text == "Active 12m ago", text

    def test_hours_ago(self, demo1_auth, demo2_auth, mongo_db):
        # 3 hours ago → "Active 3h ago" (delta.days==0)
        when = datetime.now(timezone.utc) - timedelta(hours=3, minutes=5)
        text = self._set_la_and_get(demo1_auth, demo2_auth, mongo_db, when)
        assert text == "Active 3h ago", text

    def test_yesterday(self, demo1_auth, demo2_auth, mongo_db):
        # ~30 hours ago → delta.days==1 → "Active yesterday"
        when = datetime.now(timezone.utc) - timedelta(hours=30)
        text = self._set_la_and_get(demo1_auth, demo2_auth, mongo_db, when)
        assert text == "Active yesterday", text

    def test_days_ago(self, demo1_auth, demo2_auth, mongo_db):
        # 3 days ago → "Active 3d ago"
        when = datetime.now(timezone.utc) - timedelta(days=3, hours=2)
        text = self._set_la_and_get(demo1_auth, demo2_auth, mongo_db, when)
        assert text == "Active 3d ago", text

    def test_weeks_ago(self, demo1_auth, demo2_auth, mongo_db):
        # 14 days ago → days<30 → "Active 2w ago"
        when = datetime.now(timezone.utc) - timedelta(days=14)
        text = self._set_la_and_get(demo1_auth, demo2_auth, mongo_db, when)
        assert text == "Active 2w ago", text

    def test_months_ago(self, demo1_auth, demo2_auth, mongo_db):
        # 90 days ago → "Active 3mo ago"
        when = datetime.now(timezone.utc) - timedelta(days=90)
        text = self._set_la_and_get(demo1_auth, demo2_auth, mongo_db, when)
        assert text == "Active 3mo ago", text


# ==================== IS_ONLINE FLAG ====================

class TestIsOnlineFlag:
    """is_online should be true iff last_active < 5min."""

    def test_online_when_recent(self, demo1_auth, demo2_auth, mongo_db):
        original = mongo_db.users.find_one({"id": demo2_auth["user_id"]}, {"last_active": 1}).get("last_active")
        try:
            mongo_db.users.update_one(
                {"id": demo2_auth["user_id"]},
                {"$set": {"last_active": (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()}}
            )
            r = requests.get(f"{BASE_URL}/api/profile/{demo2_auth['user_id']}", headers=demo1_auth["headers"], timeout=30)
            assert r.status_code == 200
            assert r.json().get("is_online") is True
        finally:
            if original:
                mongo_db.users.update_one({"id": demo2_auth["user_id"]}, {"$set": {"last_active": original}})

    def test_offline_when_old(self, demo1_auth, demo2_auth, mongo_db):
        original = mongo_db.users.find_one({"id": demo2_auth["user_id"]}, {"last_active": 1}).get("last_active")
        try:
            mongo_db.users.update_one(
                {"id": demo2_auth["user_id"]},
                {"$set": {"last_active": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()}}
            )
            r = requests.get(f"{BASE_URL}/api/profile/{demo2_auth['user_id']}", headers=demo1_auth["headers"], timeout=30)
            assert r.status_code == 200
            assert r.json().get("is_online") is False
        finally:
            if original:
                mongo_db.users.update_one({"id": demo2_auth["user_id"]}, {"$set": {"last_active": original}})
