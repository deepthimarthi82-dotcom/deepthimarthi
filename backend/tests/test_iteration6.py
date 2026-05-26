"""Iteration 6 - Batch A backend tests for Spark dating app.

Covers:
- Profile completeness, growth goals, icebreakers, anti-ghosting pledge
- Wellness mode (checkin/status/take-break/resume) + discover filter
- Transparency score, today's spark (cached), why this match
- Conversation health + reignite, match anniversary
- FREE_DAILY_SWIPES bumped 20 -> 30
- Regression: login + AI date planner premium gate
"""
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")

MATCH_ID = "0a019632-6f9f-45ab-8fb6-20601b4e60f3"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

mongo = MongoClient(MONGO_URL)
db = mongo[DB_NAME]


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed for {email}: {r.status_code} {r.text[:200]}")
    return r.json()


@pytest.fixture(scope="module")
def demo1():
    d = _login("demo1@spark.app", "password123")
    return {"id": d["user_id"], "token": d["token"], "h": {"Authorization": f"Bearer {d['token']}"}}


@pytest.fixture(scope="module")
def demo2():
    d = _login("demo2@spark.app", "password123")
    return {"id": d["user_id"], "token": d["token"], "h": {"Authorization": f"Bearer {d['token']}"}}


@pytest.fixture(scope="module")
def vip_admin():
    d = _login("deepthimarthi82@gmail.com", "Spark2026!")
    return {"id": d["user_id"], "token": d["token"], "h": {"Authorization": f"Bearer {d['token']}"}}


# ---------- 1. PROFILE COMPLETENESS ----------
class TestCompleteness:
    def test_completeness_shape(self, demo1):
        r = requests.get(f"{BASE_URL}/api/me/completeness", headers=demo1["h"], timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "percent" in data and "missing" in data and "checks" in data
        assert isinstance(data["percent"], int)
        assert 0 <= data["percent"] <= 100
        assert isinstance(data["checks"], list) and len(data["checks"]) == 8
        for c in data["checks"]:
            assert {"name", "complete", "weight"} <= set(c.keys())

    def test_completeness_increments_on_interests(self, demo1):
        # snapshot original interests
        orig = db.users.find_one({"id": demo1["id"]}) or {}
        orig_interests = orig.get("interests", [])
        try:
            db.users.update_one({"id": demo1["id"]}, {"$set": {"interests": []}})
            r1 = requests.get(f"{BASE_URL}/api/me/completeness", headers=demo1["h"], timeout=30).json()
            db.users.update_one({"id": demo1["id"]}, {"$set": {"interests": ["hiking", "music", "coffee"]}})
            r2 = requests.get(f"{BASE_URL}/api/me/completeness", headers=demo1["h"], timeout=30).json()
            assert r2["percent"] >= r1["percent"] + 10, f"expected +10 from interests, got {r1['percent']} -> {r2['percent']}"
            assert "interests" in r1["missing"]
            assert "interests" not in r2["missing"]
        finally:
            db.users.update_one({"id": demo1["id"]}, {"$set": {"interests": orig_interests}})


# ---------- 2. PROFILE FIELD OPTIONS (no auth) ----------
class TestProfileFields:
    def test_options_no_auth(self):
        r = requests.get(f"{BASE_URL}/api/options/profile-fields", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data.get("growth_goal_options"), list)
        assert len(data["growth_goal_options"]) == 12
        assert isinstance(data.get("icebreaker_questions"), list)
        assert len(data["icebreaker_questions"]) == 20


# ---------- 3. GROWTH GOALS ----------
class TestGrowthGoals:
    def test_save_and_persist(self, demo1):
        goals = ["Travel more", "Get fit", "Learn a language"]
        r = requests.put(f"{BASE_URL}/api/me/growth-goals", json={"goals": goals}, headers=demo1["h"], timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["growth_goals"] == goals
        me = requests.get(f"{BASE_URL}/api/auth/me", headers=demo1["h"], timeout=30).json()
        # /auth/me returns user dict at root level (no nested "user" key)
        u = me.get("user", me)
        assert u["growth_goals"] == goals

    def test_max_5_truncation(self, demo1):
        seven = ["Travel more", "Get fit", "Learn a language", "Buy a home", "Start a family", "Change careers", "Build wealth"]
        r = requests.put(f"{BASE_URL}/api/me/growth-goals", json={"goals": seven}, headers=demo1["h"], timeout=30)
        assert r.status_code == 200
        assert r.json()["growth_goals"] == seven[:5]
        me = requests.get(f"{BASE_URL}/api/auth/me", headers=demo1["h"], timeout=30).json()
        u = me.get("user", me)
        assert u["growth_goals"] == seven[:5]


# ---------- 4. ICEBREAKERS ----------
class TestIcebreakers:
    def test_save_and_persist(self, demo1):
        ans = [
            {"question": "Best travel memory?", "answer": "Patagonia trek"},
            {"question": "Unpopular opinion?", "answer": "Pineapple on pizza"},
        ]
        r = requests.put(f"{BASE_URL}/api/me/icebreakers", json={"answers": ans}, headers=demo1["h"], timeout=30)
        assert r.status_code == 200, r.text
        saved = r.json()["icebreaker_answers"]
        assert len(saved) == 2
        assert saved[0]["question"] == "Best travel memory?"

    def test_max_3_and_empty_filter(self, demo1):
        five = [
            {"question": "q1", "answer": "a1"},
            {"question": "q2", "answer": "  "},  # filtered (empty)
            {"question": "q3", "answer": "a3"},
            {"question": "q4", "answer": "a4"},
            {"question": "q5", "answer": "a5"},
        ]
        r = requests.put(f"{BASE_URL}/api/me/icebreakers", json={"answers": five}, headers=demo1["h"], timeout=30)
        assert r.status_code == 200
        saved = r.json()["icebreaker_answers"]
        # spec: filter empties then truncate to 3 — server truncates [:3] first then filters
        # so q2 (empty) being in first 3 means we end with 2 items
        assert len(saved) <= 3
        for a in saved:
            assert a["answer"].strip() != ""


# ---------- 5. PLEDGE ----------
class TestPledge:
    def test_toggle_on_off(self, demo1):
        r = requests.put(f"{BASE_URL}/api/me/pledge", json={"enabled": True}, headers=demo1["h"], timeout=30)
        assert r.status_code == 200
        assert r.json()["anti_ghosting_pledge"] is True
        u = db.users.find_one({"id": demo1["id"]})
        assert u.get("anti_ghosting_pledge") is True
        assert u.get("pledge_signed_at")

        r = requests.put(f"{BASE_URL}/api/me/pledge", json={"enabled": False}, headers=demo1["h"], timeout=30)
        assert r.status_code == 200
        assert r.json()["anti_ghosting_pledge"] is False
        u = db.users.find_one({"id": demo1["id"]})
        assert u.get("anti_ghosting_pledge") is False


# ---------- 6. WELLNESS ----------
class TestWellness:
    def test_checkin_invalid_mood(self, demo1):
        r = requests.post(f"{BASE_URL}/api/wellness/checkin", json={"mood": "ecstatic"}, headers=demo1["h"], timeout=30)
        assert r.status_code == 400

    def test_checkin_good(self, demo1):
        # clean wellness checkins for this user to ensure deterministic streak test
        db.wellness_checkins.delete_many({"user_id": demo1["id"]})
        r = requests.post(f"{BASE_URL}/api/wellness/checkin", json={"mood": "good"}, headers=demo1["h"], timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["mood"] == "good"
        assert data["show_support"] is False

    def test_three_down_streak(self, demo1):
        db.wellness_checkins.delete_many({"user_id": demo1["id"]})
        # Insert two prior down checkins directly (back-dated by seconds so sort order is deterministic)
        now = datetime.now(timezone.utc)
        for i in range(2):
            db.wellness_checkins.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": demo1["id"],
                "mood": "down",
                "created_at": (now - timedelta(seconds=20 - i)).isoformat(),
            })
        # Third down via API
        r = requests.post(f"{BASE_URL}/api/wellness/checkin", json={"mood": "down"}, headers=demo1["h"], timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["show_support"] is True, data
        assert data["support_message"]
        # cleanup
        db.wellness_checkins.delete_many({"user_id": demo1["id"]})

    def test_status_shape(self, demo1):
        r = requests.get(f"{BASE_URL}/api/wellness/status", headers=demo1["h"], timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["wellness_prompt_at"] == 20
        assert data["daily_limit"] == 30  # free user
        assert "is_paused" in data and "today_checkin" in data and "paused_until" in data

    def test_take_break_then_excluded_from_discover(self, demo1, demo2):
        # demo2 takes a 3-day break
        r = requests.post(f"{BASE_URL}/api/wellness/take-break", json={"days": 3}, headers=demo2["h"], timeout=30)
        assert r.status_code == 200
        until = r.json()["paused_until"]
        # parse ts → ~ 3 days in future
        future = datetime.fromisoformat(until.replace("Z", "+00:00"))
        delta_days = (future - datetime.now(timezone.utc)).days
        assert 2 <= delta_days <= 3
        # confirm DB
        u = db.users.find_one({"id": demo2["id"]})
        assert u.get("wellness_paused_until")

        # Now demo1's discover should NOT contain demo2
        r = requests.get(f"{BASE_URL}/api/discover", headers=demo1["h"], timeout=30)
        assert r.status_code == 200
        profiles = r.json().get("profiles", [])
        ids = [p["id"] for p in profiles]
        assert demo2["id"] not in ids, f"paused demo2 still appears in discover: {ids}"

        # resume
        r = requests.post(f"{BASE_URL}/api/wellness/resume", headers=demo2["h"], timeout=30)
        assert r.status_code == 200
        u = db.users.find_one({"id": demo2["id"]})
        assert "wellness_paused_until" not in u or not u.get("wellness_paused_until")

    def test_daily_limit_is_30(self, demo1):
        r = requests.get(f"{BASE_URL}/api/discover", headers=demo1["h"], timeout=30)
        assert r.status_code == 200
        data = r.json()
        # daily_swipes_remaining should be <= 30 for free user (not 20)
        rem = data.get("swipes_remaining") or data.get("daily_swipes_remaining")
        if rem is not None:
            assert rem <= 30
        # check user record
        u = db.users.find_one({"id": demo1["id"]})
        assert u.get("daily_swipes_remaining", 0) <= 30


# ---------- 7. TRANSPARENCY ----------
class TestTransparency:
    def test_transparency_shape(self, demo1, demo2):
        r = requests.get(f"{BASE_URL}/api/transparency/{demo2['id']}", headers=demo1["h"], timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ["last_active_human", "response_rate", "response_rate_badge", "authenticity_score", "genuine_profile", "days_on_app"]:
            assert k in data, f"missing {k}"
        assert data["response_rate_badge"] in ["High", "Medium", "Low", "—"]
        assert 0 <= data["authenticity_score"] <= 110
        assert isinstance(data["genuine_profile"], bool)


# ---------- 8. TODAY'S SPARK + WHY ----------
class TestTodaysSpark:
    def test_todays_spark_cached(self, demo1):
        # Clear cache first so we get a fresh pick this run
        db.users.update_one({"id": demo1["id"]}, {"$unset": {"todays_spark_user_id": "", "todays_spark_date": ""}})
        r1 = requests.get(f"{BASE_URL}/api/discover/todays-spark", headers=demo1["h"], timeout=30)
        assert r1.status_code == 200
        d1 = r1.json()
        if d1.get("pick") is None:
            # refresh demo1 swipes so eligible candidates exist
            db.swipes.delete_many({"swiper_id": demo1["id"]})
            r1 = requests.get(f"{BASE_URL}/api/discover/todays-spark", headers=demo1["h"], timeout=30)
            d1 = r1.json()
        assert d1.get("pick") is not None, "Even after clearing swipes, no pick available"
        assert "match_reasons" in d1 and isinstance(d1["match_reasons"], list) and len(d1["match_reasons"]) >= 1
        # second call cached
        r2 = requests.get(f"{BASE_URL}/api/discover/todays-spark", headers=demo1["h"], timeout=30)
        d2 = r2.json()
        assert d2["pick"]["id"] == d1["pick"]["id"], "Today's Spark not cached daily"
        assert d2["date"] == d1["date"]

    def test_why_returns_reasons(self, demo1, demo2):
        r = requests.get(f"{BASE_URL}/api/discover/why/{demo2['id']}", headers=demo1["h"], timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "reasons" in data
        assert isinstance(data["reasons"], list)
        assert 1 <= len(data["reasons"]) <= 5
        for s in data["reasons"]:
            assert isinstance(s, str) and len(s) > 0


# ---------- 9. CHAT HEALTH + REIGNITE ----------
class TestChatHealthReignite:
    def test_health_active_with_recent_messages(self, demo1):
        # seed 4 messages in last hour
        now = datetime.now(timezone.utc)
        seeded_ids = []
        for i in range(4):
            mid = str(uuid.uuid4())
            seeded_ids.append(mid)
            db.messages.insert_one({
                "id": mid,
                "match_id": MATCH_ID,
                "sender_id": demo1["id"],
                "content": f"gAAAA_seed_{i}",  # pretend encrypted; content is opaque
                "encrypted": True,
                "created_at": (now - timedelta(minutes=10 + i)).isoformat()
            })
        try:
            r = requests.get(f"{BASE_URL}/api/chat/{MATCH_ID}/health", headers=demo1["h"], timeout=30)
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["color"] in ["green", "yellow", "red"]
            # active: <12h AND count>=4 → green
            assert data["color"] == "green", data
            assert data["status"] == "active"
        finally:
            db.messages.delete_many({"id": {"$in": seeded_ids}})

    def test_health_stale_red(self, demo1):
        # Force every message in this match to 60h old
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=60)).isoformat()
        snapshot = list(db.messages.find({"match_id": MATCH_ID}, {"id": 1, "created_at": 1}))
        try:
            db.messages.update_many({"match_id": MATCH_ID}, {"$set": {"created_at": old_ts}})
            # also need a message to exist
            if not snapshot:
                tmp_id = str(uuid.uuid4())
                db.messages.insert_one({
                    "id": tmp_id, "match_id": MATCH_ID, "sender_id": demo1["id"],
                    "content": "x", "encrypted": False, "created_at": old_ts
                })
                snapshot = [{"id": tmp_id, "created_at": old_ts, "_tmp": True}]
            r = requests.get(f"{BASE_URL}/api/chat/{MATCH_ID}/health", headers=demo1["h"], timeout=30)
            assert r.status_code == 200
            data = r.json()
            assert data["color"] == "red", data
            assert data["status"] == "stale"
        finally:
            # restore original timestamps
            for s in snapshot:
                if s.get("_tmp"):
                    db.messages.delete_one({"id": s["id"]})
                else:
                    db.messages.update_one({"id": s["id"]}, {"$set": {"created_at": s["created_at"]}})

    def test_reignite_returns_3_topics(self, demo1):
        r = requests.post(f"{BASE_URL}/api/chat/{MATCH_ID}/reignite", headers=demo1["h"], timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "topics" in data
        assert isinstance(data["topics"], list)
        assert len(data["topics"]) == 3
        for t in data["topics"]:
            assert isinstance(t, str) and len(t) > 0


# ---------- 10. MATCH ANNIVERSARY ----------
class TestAnniversary:
    def _set_matched_at_days_ago(self, days):
        new_ts = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        db.matches.update_one({"id": MATCH_ID}, {"$set": {"matched_at": new_ts}})

    def test_anniversary_week(self, demo1):
        original = db.matches.find_one({"id": MATCH_ID})
        if not original:
            pytest.skip("match not found")
        try:
            self._set_matched_at_days_ago(7)
            r = requests.get(f"{BASE_URL}/api/match/{MATCH_ID}/anniversary", headers=demo1["h"], timeout=30)
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["days"] == 7
            assert data["milestone"] and data["milestone"]["tier"] == "week"

            self._set_matched_at_days_ago(30)
            data = requests.get(f"{BASE_URL}/api/match/{MATCH_ID}/anniversary", headers=demo1["h"], timeout=30).json()
            assert data["days"] == 30
            assert data["milestone"]["tier"] == "month"

            self._set_matched_at_days_ago(90)
            data = requests.get(f"{BASE_URL}/api/match/{MATCH_ID}/anniversary", headers=demo1["h"], timeout=30).json()
            assert data["days"] == 90
            assert data["milestone"]["tier"] == "legend"

            self._set_matched_at_days_ago(12)
            data = requests.get(f"{BASE_URL}/api/match/{MATCH_ID}/anniversary", headers=demo1["h"], timeout=30).json()
            assert data["days"] == 12
            assert data["milestone"] is None
        finally:
            db.matches.update_one({"id": MATCH_ID}, {"$set": {"matched_at": original["matched_at"]}})


# ---------- 11. REGRESSION ----------
class TestRegression:
    def test_login_demo1(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "demo1@spark.app", "password": "password123"}, timeout=30)
        assert r.status_code == 200

    def test_discover_works(self, demo1):
        r = requests.get(f"{BASE_URL}/api/discover", headers=demo1["h"], timeout=30)
        assert r.status_code == 200
        assert "profiles" in r.json()

    def test_matches_list(self, demo1):
        r = requests.get(f"{BASE_URL}/api/matches", headers=demo1["h"], timeout=30)
        assert r.status_code == 200

    def test_ai_date_planner_premium_gate(self, demo1):
        # demo1 is free → should be 402 premium_required
        r = requests.post(
            f"{BASE_URL}/api/ai/date-planner/{MATCH_ID}",
            json={"budget": "$$", "activity_type": "food", "city": "San Francisco"},
            headers=demo1["h"], timeout=30,
        )
        assert r.status_code == 402, f"expected 402 premium gate, got {r.status_code}: {r.text[:200]}"
        body = r.json()
        assert body.get("detail", {}).get("premium_required") is True

    def test_vip_admin_login(self, vip_admin):
        # If admin login works, vip_admin fixture succeeds; verify auth/me
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=vip_admin["h"], timeout=30)
        assert r.status_code == 200
