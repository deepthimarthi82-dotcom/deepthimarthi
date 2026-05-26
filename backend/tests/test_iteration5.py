"""
Iteration 5 — Security batch backend tests for Spark.

Covers: Password strength, 18+ DOB block, JWT 30-day, bcrypt rounds=12,
AES message encryption (Fernet), 2FA toggle/login/verify, account
deletion (request/cancel/confirm), CCPA data export ZIP, Private Mode
toggle (premium-only), enhanced block (deletes matches+messages+swipes),
admin security flags, security headers, suspicious activity detection,
rate limiting on /auth/register and /auth/login (RUN LAST — poisons
the in-memory bucket for ~60s).
"""
import io
import os
import time
import uuid
import zipfile
import json
import asyncio
import pytest
import requests
import jwt as pyjwt
import bcrypt
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

# Use REACT_APP_BACKEND_URL from /app/frontend/.env
BASE_URL = ""
try:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
except Exception:
    pass

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN_EMAIL = "deepthimarthi82@gmail.com"
ADMIN_PASSWORD = "Spark2026!"
ADMIN2_EMAIL = "vikaskesiraju@gmail.com"
DEMO1 = {"email": "demo1@spark.app", "password": "password123"}
DEMO2 = {"email": "demo2@spark.app", "password": "password123"}


# ---------- module-level helpers ----------
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=30)
    return r


def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def run_async(coro):
    """Run an async coroutine from sync test code."""
    return asyncio.get_event_loop().run_until_complete(coro) if not asyncio.get_event_loop().is_running() else asyncio.run(coro)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def db():
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


@pytest.fixture(scope="session")
def demo1_token(event_loop):
    r = login(**DEMO1)
    if r.status_code != 200:
        # demo1 may have 2FA on from a previous failed run — turn it off via db
        client = AsyncIOMotorClient(MONGO_URL)
        async def _disable():
            await client[DB_NAME].users.update_one(
                {"email": DEMO1["email"]},
                {"$set": {"two_factor_enabled": False, "suspended": False}, "$unset": {"suspended_reason": ""}})
        event_loop.run_until_complete(_disable())
        r = login(**DEMO1)
    assert r.status_code == 200, f"demo1 login: {r.status_code} {r.text}"
    return r.json()["token"], r.json()["user_id"]


@pytest.fixture(scope="session")
def admin_token():
    r = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    assert r.status_code == 200, f"admin login: {r.status_code} {r.text}"
    return r.json()["token"], r.json()["user_id"]


@pytest.fixture(scope="session")
def admin2_token():
    r = login(ADMIN2_EMAIL, ADMIN_PASSWORD)
    if r.status_code != 200:
        pytest.skip(f"admin2 login failed: {r.status_code}")
    return r.json()["token"], r.json()["user_id"]


# =========================================================
# 1. PASSWORD STRENGTH (uses /auth/register — RATE LIMITED 5/min)
# Run all 4 in this class within one minute, then move on.
# =========================================================
class TestPasswordStrength:
    """First 4 register calls of the test session. Stay within 5/min budget."""

    def _reg(self, email, pw, dob="1990-01-01"):
        return requests.post(f"{BASE_URL}/api/auth/register",
                             json={"email": email, "password": pw, "name": "T",
                                   "date_of_birth": dob}, timeout=30)

    def test_weak_too_short(self):
        r = self._reg(f"pw_weak_{uuid.uuid4().hex[:6]}@example.com", "weak")
        assert r.status_code == 400, r.text
        assert "8 characters" in r.json().get("detail", "")

    def test_no_special_char(self):
        r = self._reg(f"pw_nospec_{uuid.uuid4().hex[:6]}@example.com", "Strong1A")
        assert r.status_code == 400, r.text
        assert "special character" in r.json().get("detail", "")

    def test_no_digit(self):
        r = self._reg(f"pw_nodigit_{uuid.uuid4().hex[:6]}@example.com", "Strong!!!")
        assert r.status_code == 400, r.text
        assert "number" in r.json().get("detail", "")

    def test_strong_password_ok(self):
        email = f"pw_ok_{uuid.uuid4().hex[:6]}@example.com"
        r = self._reg(email, "Strong123!")
        assert r.status_code == 200, r.text
        assert "token" in r.json()
        # Cleanup
        client = AsyncIOMotorClient(MONGO_URL)
        async def _del():
            await client[DB_NAME].users.delete_one({"email": email})
        asyncio.get_event_loop().run_until_complete(_del())


# =========================================================
# 2. 18+ DOB block — we've used 4 register calls. The 5th in window must
#    be minor block. Then sleep 65s for the adult test.
# =========================================================
class TestDOBBlock:

    def test_minor_blocked_403(self, db, event_loop):
        # 5th register in window (5/min limit) — still under
        email = f"minor_{uuid.uuid4().hex[:6]}@example.com"
        r = requests.post(f"{BASE_URL}/api/auth/register",
                          json={"email": email, "password": "Strong123!",
                                "name": "Kid", "date_of_birth": "2015-01-01"}, timeout=30)
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text}"
        assert "18" in r.json().get("detail", "")

        async def _verify():
            cnt = await db.minor_block_attempts.count_documents({})
            u = await db.users.find_one({"email": email})
            return cnt, u

        cnt, u = event_loop.run_until_complete(_verify())
        assert cnt > 0, "minor_block_attempts should have at least one row"
        assert u is None, "User should NOT be created when DOB indicates minor"

    def test_adult_dob_allowed(self, db, event_loop):
        # Wait out the register rate-limit window (5/min)
        # Sleep ~65s to be safe — this is the bottleneck of the suite.
        time.sleep(65)
        email = f"adult_{uuid.uuid4().hex[:6]}@example.com"
        r = requests.post(f"{BASE_URL}/api/auth/register",
                          json={"email": email, "password": "Strong123!",
                                "name": "Adult", "date_of_birth": "1990-01-01"}, timeout=30)
        assert r.status_code == 200, f"adult register failed: {r.status_code} {r.text}"
        assert "token" in r.json()

        async def _cleanup():
            await db.users.delete_one({"email": email})
        event_loop.run_until_complete(_cleanup())


# =========================================================
# 3. JWT 30-day expiry
# =========================================================
class TestJWTExpiry:
    def test_jwt_exp_is_30_days(self, demo1_token):
        token, _ = demo1_token
        payload = pyjwt.decode(token, options={"verify_signature": False, "verify_exp": False})
        assert "exp" in payload
        exp_dt = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = exp_dt - now
        # Should be ~30 days (allow tolerance)
        assert timedelta(days=29) < delta < timedelta(days=31), \
            f"JWT exp delta is {delta}, expected ~30 days"


# =========================================================
# 4. bcrypt rounds=12
# =========================================================
class TestBcryptRounds:
    def test_user_password_hash_has_12_rounds(self, db, event_loop):
        async def _get():
            return await db.users.find_one({"email": DEMO1["email"]})
        u = event_loop.run_until_complete(_get())
        assert u is not None
        h = u["password"]
        # bcrypt hash format: $2b$12$...
        assert h.startswith("$2b$12$") or h.startswith("$2a$12$"), \
            f"Expected 12 rounds, got hash: {h[:10]}"


# =========================================================
# 5. AES-256 (Fernet) message encryption at rest
# =========================================================
class TestMessageEncryption:
    def test_message_stored_encrypted_and_decrypted_on_read(self, db, event_loop, demo1_token):
        token, demo1_id = demo1_token
        # Find existing match demo1<->demo2
        r = requests.get(f"{BASE_URL}/api/matches", headers=auth_headers(token), timeout=30)
        assert r.status_code == 200
        matches = r.json().get("matches", [])
        if not matches:
            pytest.skip("No match available for demo1")
        match_id = matches[0]["match_id"]

        secret = f"secret hello {uuid.uuid4().hex[:6]}"
        r = requests.post(f"{BASE_URL}/api/messages",
                          json={"match_id": match_id, "content": secret},
                          headers=auth_headers(token), timeout=30)
        assert r.status_code == 200, r.text
        msg_id = r.json().get("message_id") or r.json().get("id")

        async def _fetch():
            return await db.messages.find_one({"match_id": match_id, "sender_id": demo1_id},
                                              sort=[("created_at", -1)])
        raw = event_loop.run_until_complete(_fetch())
        assert raw is not None
        # DB should have encrypted:true and content starts with 'gAAAA'
        assert raw.get("encrypted") is True, f"Expected encrypted=true, got {raw.get('encrypted')}"
        assert raw["content"].startswith("gAAAA"), \
            f"Expected Fernet ciphertext (starts gAAAA), got: {raw['content'][:20]}"
        assert secret not in raw["content"], "Plaintext leaked in DB!"

        # GET messages — should be decrypted
        r2 = requests.get(f"{BASE_URL}/api/messages/{match_id}",
                          headers=auth_headers(token), timeout=30)
        assert r2.status_code == 200
        msgs = r2.json().get("messages", [])
        assert any(m.get("content") == secret for m in msgs), \
            f"Decrypted secret not found in messages response"


# =========================================================
# 6. 2FA toggle + login challenge + verify
# =========================================================
class TestTwoFactor:
    def test_2fa_full_flow(self, db, event_loop, demo1_token):
        token, demo1_id = demo1_token
        # Enable 2FA
        r = requests.post(f"{BASE_URL}/api/auth/2fa/toggle",
                          json={"enabled": True}, headers=auth_headers(token), timeout=30)
        assert r.status_code == 200, r.text
        assert r.json().get("two_factor_enabled") is True

        try:
            # Login — should NOT return token, should return two_factor_required:true
            r = login(**DEMO1)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body.get("two_factor_required") is True, f"Expected two_factor_required:true, got {body}"
            assert "token" not in body or not body.get("token"), "Login should not return token when 2FA on"

            # Fetch latest code from db
            async def _get_code():
                return await db.two_factor_codes.find_one(
                    {"user_id": demo1_id, "used": False}, sort=[("created_at", -1)])
            rec = event_loop.run_until_complete(_get_code())
            assert rec is not None, "No 2FA code in DB"
            code = rec["code"]
            assert len(code) == 6 and code.isdigit()

            # Verify
            r = requests.post(f"{BASE_URL}/api/auth/2fa/verify",
                              json={"user_id": demo1_id, "code": code}, timeout=30)
            assert r.status_code == 200, r.text
            assert "token" in r.json()

            # Replaying the same code -> 401 (now used)
            r2 = requests.post(f"{BASE_URL}/api/auth/2fa/verify",
                               json={"user_id": demo1_id, "code": code}, timeout=30)
            assert r2.status_code == 401

            # Wrong code -> 401
            r3 = requests.post(f"{BASE_URL}/api/auth/2fa/verify",
                               json={"user_id": demo1_id, "code": "000000"}, timeout=30)
            assert r3.status_code == 401

            # Expired code -> 401
            async def _make_expired():
                exp_code = f"{int(time.time()) % 900000 + 100000}"
                await db.two_factor_codes.insert_one({
                    "user_id": demo1_id, "code": exp_code,
                    "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
                    "used": False,
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                return exp_code
            exp_code = event_loop.run_until_complete(_make_expired())
            r4 = requests.post(f"{BASE_URL}/api/auth/2fa/verify",
                               json={"user_id": demo1_id, "code": exp_code}, timeout=30)
            assert r4.status_code == 401
        finally:
            # Cleanup — disable 2FA so other tests work
            # Need a fresh token because demo1_token may have been issued before 2fa was on but it's still valid
            requests.post(f"{BASE_URL}/api/auth/2fa/toggle",
                          json={"enabled": False}, headers=auth_headers(token), timeout=30)


# =========================================================
# 7. Account deletion request/cancel/confirm + Data export
# =========================================================
class TestAccountDeletion:

    def _make_temp_user(self, db, event_loop, email_prefix="del"):
        """Insert a temp user directly into db, return (user_id, token)."""
        uid = str(uuid.uuid4())
        email = f"{email_prefix}_{uuid.uuid4().hex[:6]}@example.com"
        pw_hash = bcrypt.hashpw(b"Strong123!", bcrypt.gensalt(rounds=12)).decode()
        async def _insert():
            await db.users.insert_one({
                "id": uid, "email": email, "password": pw_hash, "name": "T",
                "subscription": "free", "profile_complete": False, "quiz_complete": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_active": datetime.now(timezone.utc).isoformat(),
            })
        event_loop.run_until_complete(_insert())
        # Login to get token (login is 10/min — limit aware)
        r = login(email, "Strong123!")
        assert r.status_code == 200, r.text
        return uid, email, r.json()["token"]

    def test_delete_request_and_cancel(self, db, event_loop):
        uid, email, token = self._make_temp_user(db, event_loop, "delreq")
        try:
            r = requests.post(f"{BASE_URL}/api/account/delete/request",
                              headers=auth_headers(token), timeout=30)
            assert r.status_code == 200, r.text
            pd = r.json().get("pending_deletion_at")
            assert pd, "pending_deletion_at not returned"
            pd_dt = datetime.fromisoformat(pd)
            now = datetime.now(timezone.utc)
            delta = pd_dt - now
            assert timedelta(days=29) < delta < timedelta(days=31)

            async def _check():
                return await db.users.find_one({"id": uid})
            u = event_loop.run_until_complete(_check())
            assert u.get("pending_deletion_at"), "DB should have pending_deletion_at"

            # Cancel
            r2 = requests.post(f"{BASE_URL}/api/account/delete/cancel",
                               headers=auth_headers(token), timeout=30)
            assert r2.status_code == 200

            u2 = event_loop.run_until_complete(_check())
            assert not u2.get("pending_deletion_at"), "pending_deletion_at should be unset after cancel"
        finally:
            async def _cleanup():
                await db.users.delete_one({"id": uid})
            event_loop.run_until_complete(_cleanup())

    def test_delete_confirm_wrong_string_400(self, db, event_loop):
        uid, email, token = self._make_temp_user(db, event_loop, "delconfwrong")
        try:
            r = requests.post(f"{BASE_URL}/api/account/delete/confirm",
                              json={"confirm": "delete forever"},  # lowercase
                              headers=auth_headers(token), timeout=30)
            assert r.status_code == 400, r.text
            async def _check():
                return await db.users.find_one({"id": uid})
            u = event_loop.run_until_complete(_check())
            assert u is not None, "User should still exist when confirm string is wrong"
        finally:
            async def _cleanup():
                await db.users.delete_one({"id": uid})
            event_loop.run_until_complete(_cleanup())

    def test_delete_confirm_cascades(self, db, event_loop):
        uid, email, token = self._make_temp_user(db, event_loop, "delcasc")
        # Seed some data for this user
        async def _seed():
            await db.swipes.insert_one({"id": str(uuid.uuid4()), "swiper_id": uid, "swiped_id": "x", "action": "like", "created_at": datetime.now(timezone.utc).isoformat()})
            await db.matches.insert_one({"id": str(uuid.uuid4()), "user1_id": uid, "user2_id": "x", "created_at": datetime.now(timezone.utc).isoformat()})
            await db.messages.insert_one({"id": str(uuid.uuid4()), "sender_id": uid, "match_id": "x", "content": "hi", "created_at": datetime.now(timezone.utc).isoformat()})
        event_loop.run_until_complete(_seed())

        r = requests.post(f"{BASE_URL}/api/account/delete/confirm",
                          json={"confirm": "DELETE FOREVER"},
                          headers=auth_headers(token), timeout=30)
        assert r.status_code == 200, r.text

        async def _check():
            u = await db.users.find_one({"id": uid})
            sc = await db.swipes.count_documents({"swiper_id": uid})
            mc = await db.matches.count_documents({"$or": [{"user1_id": uid}, {"user2_id": uid}]})
            msc = await db.messages.count_documents({"sender_id": uid})
            return u, sc, mc, msc
        u, sc, mc, msc = event_loop.run_until_complete(_check())
        assert u is None
        assert sc == 0
        assert mc == 0
        assert msc == 0


# =========================================================
# 8. Data export ZIP
# =========================================================
class TestDataExport:
    def test_export_returns_zip_with_expected_files(self, demo1_token):
        token, _ = demo1_token
        r = requests.get(f"{BASE_URL}/api/account/export",
                         headers={"Authorization": f"Bearer {token}"}, timeout=60)
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/zip"), r.headers
        cd = r.headers.get("content-disposition", "")
        assert ".zip" in cd, cd

        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = set(z.namelist())
        expected = {"profile.json", "swipes.json", "matches.json",
                    "messages_sent.json", "reports_filed.json",
                    "profile_view_activity.json", "README.txt"}
        missing = expected - names
        assert not missing, f"Missing files in export ZIP: {missing}. Got: {names}"

        # Verify profile.json is valid JSON
        prof = json.loads(z.read("profile.json"))
        assert prof.get("email") == DEMO1["email"]
        assert "password" not in prof, "Password must NOT be in export!"


# =========================================================
# 9. Private Mode (premium-only)
# =========================================================
class TestPrivateMode:
    def test_free_user_gets_402(self, demo1_token, db, event_loop):
        # Ensure demo1 is currently free
        async def _ensure_free():
            await db.users.update_one({"email": DEMO1["email"]},
                                      {"$set": {"subscription": "free"}})
        event_loop.run_until_complete(_ensure_free())
        token, _ = demo1_token
        r = requests.put(f"{BASE_URL}/api/me/private-mode",
                         json={"enabled": True}, headers=auth_headers(token), timeout=30)
        assert r.status_code == 402, r.text
        detail = r.json().get("detail", {})
        if isinstance(detail, dict):
            assert detail.get("premium_required") is True

    def test_vip_admin_can_toggle(self, admin_token, db, event_loop):
        token, _ = admin_token
        r = requests.put(f"{BASE_URL}/api/me/private-mode",
                         json={"enabled": True}, headers=auth_headers(token), timeout=30)
        assert r.status_code == 200, r.text
        assert r.json().get("private_mode") is True
        # cleanup
        requests.put(f"{BASE_URL}/api/me/private-mode",
                     json={"enabled": False}, headers=auth_headers(token), timeout=30)


# =========================================================
# 10. Enhanced block — deletes matches+messages+swipes
# =========================================================
class TestEnhancedBlock:
    def test_block_cascades(self, db, event_loop):
        # Create two temp users + match + message + swipe in DB
        uid_a = str(uuid.uuid4())
        uid_b = str(uuid.uuid4())
        email_a = f"blkA_{uuid.uuid4().hex[:6]}@example.com"
        email_b = f"blkB_{uuid.uuid4().hex[:6]}@example.com"
        pw_hash = bcrypt.hashpw(b"Strong123!", bcrypt.gensalt(rounds=12)).decode()
        match_id = str(uuid.uuid4())

        async def _seed():
            await db.users.insert_one({
                "id": uid_a, "email": email_a, "password": pw_hash, "name": "A",
                "subscription": "free", "created_at": datetime.now(timezone.utc).isoformat()})
            await db.users.insert_one({
                "id": uid_b, "email": email_b, "password": pw_hash, "name": "B",
                "subscription": "free", "created_at": datetime.now(timezone.utc).isoformat()})
            await db.matches.insert_one({
                "id": match_id, "user1_id": uid_a, "user2_id": uid_b,
                "created_at": datetime.now(timezone.utc).isoformat()})
            await db.messages.insert_one({
                "id": str(uuid.uuid4()), "match_id": match_id, "sender_id": uid_a,
                "content": "hello", "created_at": datetime.now(timezone.utc).isoformat()})
            await db.swipes.insert_one({
                "id": str(uuid.uuid4()), "swiper_id": uid_a, "swiped_id": uid_b,
                "action": "like", "created_at": datetime.now(timezone.utc).isoformat()})
            await db.swipes.insert_one({
                "id": str(uuid.uuid4()), "swiper_id": uid_b, "swiped_id": uid_a,
                "action": "like", "created_at": datetime.now(timezone.utc).isoformat()})
        event_loop.run_until_complete(_seed())

        try:
            # Build JWT directly (bypass login rate limit & possible auth issues)
            JWT_SECRET = os.environ.get("JWT_SECRET", "spark-dating-secret-key-2024")
            token = pyjwt.encode({
                "user_id": uid_a, "email": email_a,
                "exp": datetime.now(timezone.utc) + timedelta(hours=1)
            }, JWT_SECRET, algorithm="HS256")

            r2 = requests.post(f"{BASE_URL}/api/safety/block/{uid_b}",
                               headers=auth_headers(token), timeout=30)
            assert r2.status_code == 200, r2.text

            async def _check():
                m = await db.matches.count_documents({"$or": [
                    {"user1_id": uid_a, "user2_id": uid_b},
                    {"user1_id": uid_b, "user2_id": uid_a}]})
                msg = await db.messages.count_documents({"match_id": match_id})
                sw = await db.swipes.count_documents({"$or": [
                    {"swiper_id": uid_a, "swiped_id": uid_b},
                    {"swiper_id": uid_b, "swiped_id": uid_a}]})
                return m, msg, sw
            m, msg, sw = event_loop.run_until_complete(_check())
            assert m == 0, f"Match should be deleted, found {m}"
            assert msg == 0, f"Messages should be deleted, found {msg}"
            assert sw == 0, f"Swipes should be deleted, found {sw}"
        finally:
            async def _cleanup():
                await db.users.delete_many({"id": {"$in": [uid_a, uid_b]}})
            event_loop.run_until_complete(_cleanup())


# =========================================================
# 11. Admin security endpoints
# =========================================================
class TestAdminSecurity:
    def test_non_admin_403(self, demo1_token):
        token, _ = demo1_token
        r = requests.get(f"{BASE_URL}/api/admin/security/flags",
                         headers=auth_headers(token), timeout=30)
        assert r.status_code == 403, r.text

    def test_admin_lists_flags(self, admin_token, db, event_loop):
        token, _ = admin_token
        # Seed a flag
        flag_id = str(uuid.uuid4())
        target_uid = str(uuid.uuid4())
        async def _seed():
            await db.users.insert_one({
                "id": target_uid, "email": f"flagged_{uuid.uuid4().hex[:6]}@example.com",
                "password": "x", "name": "F", "subscription": "free",
                "created_at": datetime.now(timezone.utc).isoformat()})
            await db.security_flags.insert_one({
                "id": flag_id, "user_id": target_uid, "reason": "messaging_spam",
                "severity": "high", "status": "open",
                "created_at": datetime.now(timezone.utc).isoformat()})
        event_loop.run_until_complete(_seed())

        try:
            r = requests.get(f"{BASE_URL}/api/admin/security/flags",
                             headers=auth_headers(token), timeout=30)
            assert r.status_code == 200, r.text
            flags = r.json().get("flags", [])
            assert any(f["id"] == flag_id for f in flags), "seeded flag missing"

            # Resolve with suspend
            r2 = requests.post(f"{BASE_URL}/api/admin/security/resolve/{flag_id}",
                               json={"action": "suspend"},
                               headers=auth_headers(token), timeout=30)
            assert r2.status_code == 200, r2.text
            async def _check_susp():
                return await db.users.find_one({"id": target_uid})
            u = event_loop.run_until_complete(_check_susp())
            assert u.get("suspended") is True

            # Unsuspend (new flag needed since previous is resolved)
            flag2 = str(uuid.uuid4())
            async def _seed2():
                await db.security_flags.insert_one({
                    "id": flag2, "user_id": target_uid, "reason": "manual",
                    "severity": "low", "status": "open",
                    "created_at": datetime.now(timezone.utc).isoformat()})
            event_loop.run_until_complete(_seed2())
            r3 = requests.post(f"{BASE_URL}/api/admin/security/resolve/{flag2}",
                               json={"action": "unsuspend"},
                               headers=auth_headers(token), timeout=30)
            assert r3.status_code == 200
            u2 = event_loop.run_until_complete(_check_susp())
            assert not u2.get("suspended"), "User should be unsuspended"

            # Dismiss
            flag3 = str(uuid.uuid4())
            async def _seed3():
                await db.security_flags.insert_one({
                    "id": flag3, "user_id": target_uid, "reason": "manual",
                    "severity": "low", "status": "open",
                    "created_at": datetime.now(timezone.utc).isoformat()})
            event_loop.run_until_complete(_seed3())
            r4 = requests.post(f"{BASE_URL}/api/admin/security/resolve/{flag3}",
                               json={"action": "dismiss"},
                               headers=auth_headers(token), timeout=30)
            assert r4.status_code == 200
            async def _check_flag():
                return await db.security_flags.find_one({"id": flag3})
            f = event_loop.run_until_complete(_check_flag())
            assert f.get("status") == "resolved"
        finally:
            async def _cleanup():
                await db.users.delete_one({"id": target_uid})
                await db.security_flags.delete_many({"user_id": target_uid})
            event_loop.run_until_complete(_cleanup())


# =========================================================
# 12. Security headers
# =========================================================
class TestSecurityHeaders:
    def test_headers_present(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=30)
        assert r.status_code == 200
        assert r.headers.get("X-Content-Type-Options") == "nosniff", r.headers
        assert r.headers.get("X-Frame-Options") == "DENY", r.headers
        assert "Strict-Transport-Security" in r.headers, r.headers


# =========================================================
# 13. Suspicious activity detection — call helpers directly
# =========================================================
class TestSuspiciousActivity:
    def test_messaging_spam_flag_via_seed_and_helper(self, db, event_loop):
        # Create temp user
        uid = str(uuid.uuid4())
        email = f"spam_{uuid.uuid4().hex[:6]}@example.com"
        async def _seed():
            await db.users.insert_one({
                "id": uid, "email": email, "password": "x", "name": "S",
                "subscription": "premium",
                "created_at": datetime.now(timezone.utc).isoformat()})
            # Insert 51 messages within last hour
            now = datetime.now(timezone.utc)
            docs = [{"id": str(uuid.uuid4()), "sender_id": uid, "match_id": "x",
                     "content": "spam", "created_at": now.isoformat()} for _ in range(51)]
            await db.messages.insert_many(docs)
        event_loop.run_until_complete(_seed())

        try:
            # Call helper directly via import — server.py exposes check_suspicious_messaging
            import sys
            sys.path.insert(0, "/app/backend")
            from server import check_suspicious_messaging
            event_loop.run_until_complete(check_suspicious_messaging(uid))

            async def _check():
                flag = await db.security_flags.find_one({"user_id": uid, "reason": "messaging_spam"})
                u = await db.users.find_one({"id": uid})
                return flag, u
            flag, u = event_loop.run_until_complete(_check())
            assert flag is not None, "Expected messaging_spam flag"
            assert flag.get("severity") == "high"
            assert u.get("suspended") is True, "User should be auto-suspended on high severity"
        finally:
            async def _cleanup():
                await db.messages.delete_many({"sender_id": uid})
                await db.security_flags.delete_many({"user_id": uid})
                await db.users.delete_one({"id": uid})
            event_loop.run_until_complete(_cleanup())

    def test_swipe_bot_flag(self, db, event_loop):
        uid = str(uuid.uuid4())
        async def _seed():
            await db.users.insert_one({
                "id": uid, "email": f"bot_{uuid.uuid4().hex[:6]}@example.com", "password": "x",
                "name": "B", "subscription": "free",
                "created_at": datetime.now(timezone.utc).isoformat()})
            now = datetime.now(timezone.utc)
            docs = [{"id": str(uuid.uuid4()), "swiper_id": uid, "swiped_id": str(uuid.uuid4()),
                     "action": "like", "created_at": now.isoformat()} for _ in range(30)]
            await db.swipes.insert_many(docs)
        event_loop.run_until_complete(_seed())
        try:
            import sys
            sys.path.insert(0, "/app/backend")
            from server import check_suspicious_swiping
            event_loop.run_until_complete(check_suspicious_swiping(uid))
            async def _check():
                return await db.security_flags.find_one({"user_id": uid, "reason": "swipe_bot_behavior"})
            f = event_loop.run_until_complete(_check())
            assert f is not None
            assert f.get("severity") == "high"
        finally:
            async def _cleanup():
                await db.swipes.delete_many({"swiper_id": uid})
                await db.security_flags.delete_many({"user_id": uid})
                await db.users.delete_one({"id": uid})
            event_loop.run_until_complete(_cleanup())


# =========================================================
# 14. Regression — discover still works
# =========================================================
class TestRegression:
    def test_discover_still_works(self, demo1_token):
        token, _ = demo1_token
        r = requests.get(f"{BASE_URL}/api/discover",
                         headers=auth_headers(token), timeout=30)
        assert r.status_code == 200, r.text

    def test_login_still_works(self):
        r = login(**DEMO2)
        assert r.status_code == 200, r.text


# =========================================================
# 15. RATE LIMITING — RUN LAST (poisons in-memory bucket for ~60s).
#     Use zz_ prefix on class to push to end alphabetically; pytest
#     runs in file order anyway but this is belt-and-suspenders.
# =========================================================
class TestZZRateLimiting:
    def test_login_rate_limit_429(self):
        # 25 rapid bad-cred logins; should 429 well before all complete (10/min limit)
        last_status = None
        got_429 = False
        for i in range(25):
            r = requests.post(f"{BASE_URL}/api/auth/login",
                              json={"email": f"nope_{i}@example.com", "password": "wrong"},
                              timeout=15)
            last_status = r.status_code
            if r.status_code == 429:
                got_429 = True
                break
        assert got_429, f"Expected 429 within 25 calls, last status={last_status}"

    def test_register_rate_limit_429(self):
        # Sleep to ensure we're starting a fresh window for register if needed
        time.sleep(2)
        got_429 = False
        statuses = []
        for i in range(15):
            r = requests.post(f"{BASE_URL}/api/auth/register",
                              json={"email": f"rl_{uuid.uuid4().hex[:6]}@example.com",
                                    "password": "Strong123!", "name": "RL",
                                    "date_of_birth": "1990-01-01"}, timeout=15)
            statuses.append(r.status_code)
            if r.status_code == 429:
                got_429 = True
                break
        assert got_429, f"Expected 429 within 15 register calls. Statuses: {statuses}"
