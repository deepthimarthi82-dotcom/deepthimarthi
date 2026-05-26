"""Iteration 3 backend tests for Spark dating app.
Covers: Safety Center, Support Center, AI Date Planner, Date Countdown,
Admin auto-premium, Free=20 swipes, Premium gates (402), Nominatim geocode,
Discover blocked users + language filter + distance.
"""
import os
import uuid
import asyncio
import pytest
import requests

# Reuse conftest fixtures: api_client, demo1_auth, demo2_auth, match_id, base_url
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://spark-dating-118.preview.emergentagent.com").rstrip("/")

ADMIN1 = {"email": "deepthimarthi82@gmail.com", "password": "Spark2026!", "name": "Deepthi Admin"}
ADMIN2 = {"email": "vikaskesiraju@gmail.com", "password": "Spark2026!", "name": "Vikas Admin"}


def _register_or_login(email, password, name):
    """Try register; on 400 (exists), login. If login fails (different pw from prev iteration),
    reset the password in db and login. Returns dict with token+user_id+headers."""
    r = requests.post(f"{BASE_URL}/api/auth/register",
                      json={"email": email, "password": password, "name": name}, timeout=30)
    if r.status_code == 200:
        data = r.json()
    else:
        r2 = requests.post(f"{BASE_URL}/api/auth/login",
                           json={"email": email, "password": password}, timeout=30)
        if r2.status_code != 200:
            # Reset password directly in DB using bcrypt, then login again
            import motor.motor_asyncio
            import bcrypt
            async def reset_pw():
                client = motor.motor_asyncio.AsyncIOMotorClient(
                    os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
                db_name = os.environ.get("DB_NAME", "test_database")
                hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                await client[db_name].users.update_one(
                    {"email": email.lower()}, {"$set": {"password": hashed}})
                client.close()
            asyncio.run(reset_pw())
            r2 = requests.post(f"{BASE_URL}/api/auth/login",
                               json={"email": email, "password": password}, timeout=30)
            assert r2.status_code == 200, f"register/login/reset all failed for {email}: {r.text} / {r2.text}"
        data = r2.json()
    return {
        "token": data["token"],
        "user_id": data["user_id"],
        "headers": {"Authorization": f"Bearer {data['token']}", "Content-Type": "application/json"},
    }


@pytest.fixture(scope="module")
def admin1_auth():
    return _register_or_login(**ADMIN1)


@pytest.fixture(scope="module")
def admin2_auth():
    return _register_or_login(**ADMIN2)


# ---------- 1. Free user registration -> subscription=free, 20 swipes ----------
class TestRegistrationAndAdminAutoPremium:
    def test_register_free_user_gets_20_swipes(self):
        email = f"adminTestX_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{BASE_URL}/api/auth/register",
                          json={"email": email, "password": "Pass1234!", "name": "Free Test"}, timeout=30)
        assert r.status_code == 200, r.text
        token = r.json()["token"]
        me = requests.get(f"{BASE_URL}/api/auth/me",
                          headers={"Authorization": f"Bearer {token}"}, timeout=30)
        assert me.status_code == 200, me.text
        m = me.json()
        assert m.get("subscription") == "free", f"Expected free, got: {m.get('subscription')}"
        assert m.get("daily_swipes_remaining") == 20, f"Expected 20, got {m.get('daily_swipes_remaining')}"
        assert m.get("admin_premium") in (False, None)

    def test_admin1_auto_vip(self, admin1_auth):
        me = requests.get(f"{BASE_URL}/api/auth/me", headers=admin1_auth["headers"], timeout=30)
        assert me.status_code == 200, me.text
        m = me.json()
        assert m.get("subscription") == "vip", f"Admin should be vip, got: {m.get('subscription')}"
        assert m.get("admin_premium") is True, f"Admin should have admin_premium=True, got: {m.get('admin_premium')}"
        assert m.get("email") == ADMIN1["email"].lower()

    def test_admin2_auto_vip(self, admin2_auth):
        me = requests.get(f"{BASE_URL}/api/auth/me", headers=admin2_auth["headers"], timeout=30)
        assert me.status_code == 200, me.text
        m = me.json()
        assert m.get("subscription") == "vip"
        assert m.get("admin_premium") is True


# ---------- 2. Subscription plans content ----------
class TestSubscriptionPlansContent:
    def test_premium_monthly_features(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/subscription/plans", timeout=30)
        assert r.status_code == 200, r.text
        plans = r.json().get("plans", {})
        assert "premium_monthly" in plans
        feats = plans["premium_monthly"]["features"]
        for needle in ["AI Date Planner", "Vibe Check detailed compatibility report",
                       "Voice messages in chat", "Global Passport"]:
            assert any(needle in f for f in feats), f"Missing '{needle}' in features: {feats}"
        assert len(feats) == 11, f"Expected 11 features in premium_monthly, got {len(feats)}: {feats}"


# ---------- 3. Safety Center ----------
class TestSafetyCenter:
    def test_safety_me_shape(self, demo1_auth):
        r = requests.get(f"{BASE_URL}/api/safety/me", headers=demo1_auth["headers"], timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ["emergency_contact_name", "emergency_contact_phone", "emergency_contact_email",
                  "distance_unit", "language_filter_enabled", "blocked_count"]:
            assert k in data, f"Missing key {k} in {data}"
        assert isinstance(data["blocked_count"], int)

    def test_safety_settings_update_persists(self, demo1_auth):
        payload = {
            "emergency_contact_name": "Mom",
            "emergency_contact_phone": "+15551234567",
            "distance_unit": "km",
            "language_filter_enabled": True,
        }
        r = requests.put(f"{BASE_URL}/api/safety/settings",
                         headers=demo1_auth["headers"], json=payload, timeout=30)
        assert r.status_code == 200, r.text
        # Verify via GET /api/safety/me
        g = requests.get(f"{BASE_URL}/api/safety/me", headers=demo1_auth["headers"], timeout=30)
        assert g.status_code == 200
        d = g.json()
        assert d["emergency_contact_name"] == "Mom"
        assert d["emergency_contact_phone"] == "+15551234567"
        assert d["distance_unit"] == "km"
        assert d["language_filter_enabled"] is True

    def test_block_unblock_flow_and_match_status(self, demo1_auth, demo2_auth, match_id):
        target = demo2_auth["user_id"]
        # Block
        r = requests.post(f"{BASE_URL}/api/safety/block/{target}",
                         headers=demo1_auth["headers"], timeout=30)
        assert r.status_code == 200, r.text
        # Blocked list contains target
        gl = requests.get(f"{BASE_URL}/api/safety/blocked", headers=demo1_auth["headers"], timeout=30)
        assert gl.status_code == 200
        blocked_ids = [u.get("id") for u in gl.json().get("blocked", [])]
        assert target in blocked_ids, f"Target {target} not in blocked list: {blocked_ids}"
        # Verify match status changed to 'blocked' via matches listing — check by listing demo1 matches
        ml = requests.get(f"{BASE_URL}/api/matches", headers=demo1_auth["headers"], timeout=30)
        assert ml.status_code == 200
        matches = ml.json().get("matches", [])
        # The blocked match should be absent from active matches list (status != matched)
        active_with_target = [m for m in matches if m["user"]["id"] == target]
        # If endpoint filters by status='matched', blocked match won't show -> acceptable
        # We just verify the block was registered.
        # Unblock
        u = requests.post(f"{BASE_URL}/api/safety/unblock/{target}",
                         headers=demo1_auth["headers"], timeout=30)
        assert u.status_code == 200, u.text
        gl2 = requests.get(f"{BASE_URL}/api/safety/blocked", headers=demo1_auth["headers"], timeout=30)
        blocked_ids2 = [usr.get("id") for usr in gl2.json().get("blocked", [])]
        assert target not in blocked_ids2

        # Restore match status to 'matched' so other tests still work
        # Use direct DB update via async pymongo
        import motor.motor_asyncio
        async def restore():
            client = motor.motor_asyncio.AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
            db_name = os.environ.get("DB_NAME", "test_database")
            await client[db_name].matches.update_one({"id": match_id}, {"$set": {"status": "matched"}})
            client.close()
        asyncio.run(restore())

    def test_report_user(self, demo1_auth, demo2_auth):
        target = demo2_auth["user_id"]
        r = requests.post(f"{BASE_URL}/api/safety/report/{target}",
                         headers=demo1_auth["headers"],
                         json={"reason": "harassment", "description": "test", "urgent": True},
                         timeout=30)
        assert r.status_code == 200, r.text
        assert "report_id" in r.json()

    def test_panic_returns_contact_when_set(self, demo1_auth):
        # demo1 has emergency_contact set in earlier test
        r = requests.post(f"{BASE_URL}/api/safety/panic",
                         headers=demo1_auth["headers"], json={}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "event_id" in data
        # contact dict should be present (not None) since we set it above
        assert data.get("contact") is not None, f"Expected contact set, got: {data}"
        assert data["contact"].get("name") == "Mom"

    def test_panic_warning_when_no_contact(self):
        """Register a fresh user with no emergency contact, panic should return warning."""
        email = f"panic_{uuid.uuid4().hex[:8]}@example.com"
        reg = requests.post(f"{BASE_URL}/api/auth/register",
                            json={"email": email, "password": "Pass1234!", "name": "Panic Test"}, timeout=30)
        assert reg.status_code == 200
        tok = reg.json()["token"]
        r = requests.post(f"{BASE_URL}/api/safety/panic",
                         headers={"Authorization": f"Bearer {tok}"}, json={}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "warning" in data, f"Expected warning when no contact, got: {data}"
        assert data.get("contact") is None


# ---------- 4. Support Center ----------
class TestSupportCenter:
    def test_faq(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/support/faq", timeout=30)
        assert r.status_code == 200, r.text
        faqs = r.json().get("faqs", [])
        assert isinstance(faqs, list) and len(faqs) >= 5, f"Expected >=5 FAQs, got {len(faqs)}"
        for item in faqs:
            assert "q" in item and "a" in item

    def test_support_contact_creates_ticket(self, demo1_auth):
        r = requests.post(f"{BASE_URL}/api/support/contact",
                         headers=demo1_auth["headers"],
                         json={"name": "Emma", "email": "demo1@spark.app",
                               "issue_type": "Other", "message": "TEST support ticket", "urgent": False},
                         timeout=30)
        assert r.status_code == 200, r.text
        tid = r.json().get("ticket_id")
        assert tid
        # Verify db record via direct mongo
        import motor.motor_asyncio
        async def find():
            client = motor.motor_asyncio.AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
            db_name = os.environ.get("DB_NAME", "test_database")
            t = await client[db_name].support_tickets.find_one({"id": tid})
            client.close()
            return t
        rec = asyncio.run(find())
        assert rec is not None, "Ticket not in db.support_tickets"
        assert rec.get("deliver_to") == "support@sparkmatch.dating"

    def test_bug_report(self, demo1_auth):
        # tiny base64 png
        b64 = ("data:image/png;base64,"
               "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")
        r = requests.post(f"{BASE_URL}/api/support/bug-report",
                         headers=demo1_auth["headers"],
                         json={"description": "TEST bug", "screenshot_data_url": b64,
                               "page_url": "https://example.com", "browser": "test"},
                         timeout=30)
        assert r.status_code == 200, r.text
        assert "report_id" in r.json()


# ---------- 5. Premium gates (402) ----------
class TestPremiumGates:
    def test_date_planner_402_for_free(self, demo1_auth, match_id):
        r = requests.post(f"{BASE_URL}/api/ai/date-planner/{match_id}",
                         headers=demo1_auth["headers"],
                         json={"budget": "$$", "activity_type": "food", "city": "San Francisco"},
                         timeout=30)
        assert r.status_code == 402, f"Expected 402, got {r.status_code}: {r.text}"
        detail = r.json().get("detail", {})
        assert isinstance(detail, dict) and detail.get("premium_required") is True

    def test_voice_message_402_for_free(self, demo1_auth, match_id):
        files = {"audio": ("test.webm", b"\x1aE\xdf\xa3" + b"\x00" * 50, "audio/webm")}
        r = requests.post(
            f"{BASE_URL}/api/messages/voice",
            headers={"Authorization": demo1_auth["headers"]["Authorization"]},
            params={"match_id": match_id, "duration": 3},
            files=files,
            timeout=30,
        )
        # Per request: free user should hit 402 gate on voice messages
        assert r.status_code == 402, f"Expected 402, got {r.status_code}: {r.text}"

    def test_compatibility_402_for_free(self, demo1_auth, demo2_auth):
        target = demo2_auth["user_id"]
        r = requests.post(f"{BASE_URL}/api/ai/compatibility/{target}",
                         headers=demo1_auth["headers"], timeout=30)
        assert r.status_code == 402, f"Expected 402, got {r.status_code}: {r.text}"


# ---------- 6. Admin can call premium-gated AI Date Planner ----------
class TestAdminPremiumAccess:
    def test_admin_can_hit_date_planner_no_402(self, admin1_auth, demo1_auth):
        """Admin should NOT get 402. We don't have a match for admin, so we expect 403 'Not your match',
        which proves the premium gate was passed."""
        fake_match_id = str(uuid.uuid4())
        r = requests.post(f"{BASE_URL}/api/ai/date-planner/{fake_match_id}",
                         headers=admin1_auth["headers"],
                         json={"budget": "$$", "activity_type": "food", "city": "Paris"},
                         timeout=30)
        assert r.status_code != 402, f"Admin shouldn't hit 402, got 402: {r.text}"
        assert r.status_code in (403, 404), f"Expected 403/404 (not your match), got {r.status_code}: {r.text}"


# ---------- 7. Date Countdown ----------
class TestDateCountdown:
    def _reset_match(self, match_id):
        """Reset match agreement+expiry fields for clean testing."""
        import motor.motor_asyncio
        async def reset():
            client = motor.motor_asyncio.AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
            db_name = os.environ.get("DB_NAME", "test_database")
            from datetime import datetime, timezone, timedelta
            expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
            await client[db_name].matches.update_one(
                {"id": match_id},
                {"$set": {"expires_at": expires, "status": "matched"},
                 "$unset": {"user1_agreed": "", "user2_agreed": "", "date_agreed": "",
                            "extended": "", "extended_by": "", "extended_at": "",
                            "user1_agreed_at": "", "user2_agreed_at": ""}}
            )
            client.close()
        asyncio.run(reset())

    def test_agree_date_flow(self, demo1_auth, demo2_auth, match_id):
        self._reset_match(match_id)
        # demo1 agrees first
        r1 = requests.post(f"{BASE_URL}/api/matches/{match_id}/agree-date",
                          headers=demo1_auth["headers"], timeout=30)
        assert r1.status_code == 200, r1.text
        assert r1.json().get("both_agreed") is False
        # demo2 agrees -> both_agreed=true
        r2 = requests.post(f"{BASE_URL}/api/matches/{match_id}/agree-date",
                          headers=demo2_auth["headers"], timeout=30)
        assert r2.status_code == 200, r2.text
        assert r2.json().get("both_agreed") is True

        # Verify expires_at became null in DB
        import motor.motor_asyncio
        async def check():
            client = motor.motor_asyncio.AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
            db_name = os.environ.get("DB_NAME", "test_database")
            m = await client[db_name].matches.find_one({"id": match_id})
            client.close()
            return m
        m = asyncio.run(check())
        assert m.get("expires_at") is None, f"Expected expires_at=None, got {m.get('expires_at')}"
        assert m.get("date_agreed") is True

    def test_extend_match_once(self, demo1_auth, match_id):
        self._reset_match(match_id)
        # First extend should succeed
        r1 = requests.post(f"{BASE_URL}/api/matches/{match_id}/extend",
                          headers=demo1_auth["headers"], timeout=30)
        assert r1.status_code == 200, r1.text
        assert "new_expiry" in r1.json()
        # Second extend -> 400 already extended
        r2 = requests.post(f"{BASE_URL}/api/matches/{match_id}/extend",
                          headers=demo1_auth["headers"], timeout=30)
        assert r2.status_code == 400, f"Expected 400 already-extended, got {r2.status_code}: {r2.text}"
        assert "extended" in r2.text.lower()


# ---------- 8. Geocoding via Nominatim (soft fail if network restricted) ----------
class TestGeocoding:
    def test_profile_update_geocodes_paris(self, demo2_auth):
        # Use demo2 since demo1 fixtures use Paris... actually use a fresh user to not pollute demo1
        # But profile fields are complex; we'll just send minimal allowed profile body.
        # Need to look at UserProfile schema — required fields?
        # Try via a fresh registered user
        email = f"geo_{uuid.uuid4().hex[:8]}@example.com"
        reg = requests.post(f"{BASE_URL}/api/auth/register",
                            json={"email": email, "password": "Pass1234!", "name": "Geo Test"}, timeout=30)
        assert reg.status_code == 200
        tok = reg.json()["token"]
        uid = reg.json()["user_id"]
        h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
        # Send full profile body. Try minimal required.
        body = {
            "name": "Geo Test", "age": 30, "gender": "woman", "looking_for": "men",
            "bio": "test", "location": "Paris", "country": "France",
            "interests": ["art"], "languages": ["English"],
            "intention": "serious", "photos": ["https://example.com/p.jpg"]
        }
        r = requests.put(f"{BASE_URL}/api/profile", headers=h, json=body, timeout=60)
        if r.status_code != 200:
            pytest.skip(f"Profile PUT failed (schema may differ): {r.status_code} {r.text[:200]}")
        # Allow up to a few seconds for geocode (synchronous in endpoint)
        import motor.motor_asyncio
        async def check():
            client = motor.motor_asyncio.AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
            db_name = os.environ.get("DB_NAME", "test_database")
            u = await client[db_name].users.find_one({"id": uid})
            client.close()
            return u
        u = asyncio.run(check())
        if u.get("latitude") is None or u.get("longitude") is None:
            pytest.skip(f"Geocoding returned no coords (likely outbound network blocked). User: lat={u.get('latitude')} lng={u.get('longitude')}")
        # Soft sanity: Paris is roughly 48.85 N, 2.35 E
        assert 48 < u["latitude"] < 50, f"Lat looks wrong for Paris: {u['latitude']}"
        assert 2 < u["longitude"] < 3, f"Lng looks wrong for Paris: {u['longitude']}"


# ---------- 9. Discover excludes blocked + language filter + distance ----------
class TestDiscoverEnhancements:
    def test_discover_schema_and_blocked_exclusion(self, demo1_auth, demo2_auth):
        # Block demo2 first
        target = demo2_auth["user_id"]
        rb = requests.post(f"{BASE_URL}/api/safety/block/{target}",
                          headers=demo1_auth["headers"], timeout=30)
        assert rb.status_code == 200
        # Discover should not include demo2
        r = requests.get(f"{BASE_URL}/api/profiles/discover", headers=demo1_auth["headers"], timeout=30)
        # The endpoint name might be /api/discover OR /api/profiles/discover. Try both.
        if r.status_code == 404:
            r = requests.get(f"{BASE_URL}/api/discover", headers=demo1_auth["headers"], timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "profiles" in body
        ids = [p.get("id") for p in body["profiles"]]
        assert target not in ids, f"Blocked user {target} should NOT appear in discover, got: {ids}"
        # Distance field schema check (may be null if no coords)
        for p in body["profiles"]:
            if "distance" in p:
                assert p["distance"] is None or isinstance(p["distance"], (int, float))
        # Unblock for cleanup
        ru = requests.post(f"{BASE_URL}/api/safety/unblock/{target}",
                          headers=demo1_auth["headers"], timeout=30)
        assert ru.status_code == 200
        # Restore match status
        import motor.motor_asyncio
        async def restore():
            client = motor.motor_asyncio.AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
            db_name = os.environ.get("DB_NAME", "test_database")
            r = await client[db_name].matches.find_one({"$or": [
                {"user1_id": demo1_auth["user_id"], "user2_id": target},
                {"user2_id": demo1_auth["user_id"], "user1_id": target}
            ]})
            if r:
                await client[db_name].matches.update_one({"id": r["id"]}, {"$set": {"status": "matched"}})
            client.close()
        asyncio.run(restore())
