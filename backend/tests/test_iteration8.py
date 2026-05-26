"""Iteration 8 — Batch C: Compatibility Timeline, First Date Script, Weekly Spark Challenge.

Tests against running backend at REACT_APP_BACKEND_URL. Uses demo1/demo2 + match
0a019632-6f9f-45ab-8fb6-20601b4e60f3. Some tests directly manipulate Mongo to set
streak / xp baseline state and restore on teardown.
"""
import os
import time
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL or "localhost" in BASE_URL:
    try:
        with open("/app/frontend/.env") as _f:
            for _l in _f:
                if _l.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = _l.split("=", 1)[1].strip().strip('"').rstrip("/")
    except Exception:
        pass
DEMO1 = {"email": "demo1@spark.app", "password": "password123"}
DEMO2 = {"email": "demo2@spark.app", "password": "password123"}

MATCH_ID = "0a019632-6f9f-45ab-8fb6-20601b4e60f3"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
# Read directly from backend env if missing
try:
    with open("/app/backend/.env") as f:
        for line in f:
            if line.startswith("MONGO_URL="):
                MONGO_URL = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("DB_NAME="):
                DB_NAME = line.split("=", 1)[1].strip().strip('"')
except Exception:
    pass

mongo = MongoClient(MONGO_URL)
db = mongo[DB_NAME]


# --------------- helpers ---------------
def _iso_week_key(dt: datetime) -> str:
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _current_week_key() -> str:
    return _iso_week_key(datetime.now(timezone.utc))


def _last_week_key() -> str:
    return _iso_week_key(datetime.now(timezone.utc) - timedelta(weeks=1))


def _two_weeks_ago_key() -> str:
    return _iso_week_key(datetime.now(timezone.utc) - timedelta(weeks=2))


@pytest.fixture(scope="module")
def demo1_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=DEMO1, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user_id"]


@pytest.fixture(scope="module")
def demo2_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=DEMO2, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user_id"]


@pytest.fixture(scope="module")
def demo3_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "demo3@spark.app", "password": "password123"}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"demo3 login failed: {r.status_code}")
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user_id"]


# =========================================================
# c1. Compatibility Timeline
# =========================================================
class TestTimeline:
    def test_membership_required_403(self, demo3_headers):
        h, _ = demo3_headers
        r = requests.get(f"{BASE_URL}/api/match/{MATCH_ID}/timeline", headers=h, timeout=60)
        assert r.status_code == 403, f"Expected 403, got {r.status_code} {r.text[:200]}"

    def test_milestones_shape_and_cache(self, demo1_headers):
        h, _ = demo1_headers
        # Clear cache so first call generates fresh
        db.compat_timelines.delete_one({"match_id": MATCH_ID})

        r1 = requests.get(f"{BASE_URL}/api/match/{MATCH_ID}/timeline", headers=h, timeout=90)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        ms = d1.get("milestones", [])
        assert 4 <= len(ms) <= 6, f"expected 4-6 milestones, got {len(ms)}"
        for m in ms:
            assert {"title", "estimated_window", "why", "confidence"}.issubset(m.keys())
            assert m["confidence"] in ("low", "medium", "high")
            assert isinstance(m["title"], str) and m["title"]
        assert d1.get("cached") in (False, None) or d1.get("cached") is False

        # Second call within 7 days → cached=true
        time.sleep(0.5)
        r2 = requests.get(f"{BASE_URL}/api/match/{MATCH_ID}/timeline", headers=h, timeout=30)
        assert r2.status_code == 200, r2.text
        d2 = r2.json()
        assert d2.get("cached") is True, f"second call not cached: {d2}"
        # same milestones
        assert d2["milestones"] == d1["milestones"]


# =========================================================
# c2. First Date Script
# =========================================================
class TestFirstDateScript:
    def test_membership_required_403(self, demo3_headers):
        h, _ = demo3_headers
        r = requests.get(f"{BASE_URL}/api/chat/{MATCH_ID}/first-date-script", headers=h, timeout=30)
        assert r.status_code == 403

    def test_locked_when_few_messages(self, demo1_headers):
        """Use a fake match between demo1+demo2 with <10 messages — but only one real match exists.
        So we simulate via a temp match id where we insert <10 messages and a match doc."""
        h, demo1_id = demo1_headers
        # create temp match
        fake_match = "test-iter8-locked-match"
        try:
            db.matches.insert_one({"id": fake_match, "user1_id": demo1_id, "user2_id": demo1_id, "matched_at": datetime.now(timezone.utc).isoformat()})
            r = requests.get(f"{BASE_URL}/api/chat/{fake_match}/first-date-script", headers=h, timeout=30)
            assert r.status_code == 200, r.text
            d = r.json()
            assert d["unlocked"] is False
            assert d["messages_so_far"] == 0
            assert d["messages_needed"] == 10
        finally:
            db.matches.delete_one({"id": fake_match})

    def test_unlocked_script_and_cache(self, demo1_headers):
        h, _ = demo1_headers
        # ensure message count >= 10 for MATCH_ID
        msgs = db.messages.count_documents({"match_id": MATCH_ID})
        if msgs < 10:
            pytest.skip(f"only {msgs} messages on real match — Batch B note said >10")

        db.first_date_scripts.delete_one({"match_id": MATCH_ID})
        r1 = requests.get(f"{BASE_URL}/api/chat/{MATCH_ID}/first-date-script", headers=h, timeout=120)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["unlocked"] is True
        s = d1["script"]
        assert isinstance(s.get("openers"), list) and len(s["openers"]) == 4
        assert isinstance(s.get("deeper_questions"), list) and len(s["deeper_questions"]) == 4
        assert isinstance(s.get("topics_to_avoid"), list) and len(s["topics_to_avoid"]) == 3
        assert isinstance(s.get("venue_suggestions"), list) and len(s["venue_suggestions"]) == 3
        for v in s["venue_suggestions"]:
            assert "name" in v and "why" in v
        assert isinstance(s.get("tone"), str) and s["tone"]

        # 2nd call → cached
        r2 = requests.get(f"{BASE_URL}/api/chat/{MATCH_ID}/first-date-script", headers=h, timeout=30)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2.get("cached") is True
        assert d2["script"] == d1["script"]


# =========================================================
# c3. Weekly Spark Challenge
# =========================================================
class TestWeeklyChallenge:
    def test_get_weekly_shape(self, demo1_headers):
        h, _ = demo1_headers
        r = requests.get(f"{BASE_URL}/api/challenges/weekly", headers=h, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("week_key", "challenge", "completed", "xp", "level_info", "streak_weeks", "badges"):
            assert k in d, f"missing {k}"
        c = d["challenge"]
        for k in ("id", "title", "description", "xp", "cta", "verb"):
            assert k in c
        li = d["level_info"]
        for k in ("level", "xp_current", "xp_for_next", "xp_in_level", "xp_needed_for_next"):
            assert k in li

    def test_complete_nonexistent_404(self, demo1_headers):
        h, _ = demo1_headers
        r = requests.post(f"{BASE_URL}/api/challenges/nope-not-real/complete", headers=h, timeout=30)
        assert r.status_code == 404, f"Expected 404 got {r.status_code} {r.text[:200]}"

    def test_complete_idempotent_no_double_xp(self, demo1_headers):
        """Calling complete twice on same challenge in same week → 2nd returns already_completed=true and no extra XP."""
        h, user_id = demo1_headers
        # Get active challenge id
        r = requests.get(f"{BASE_URL}/api/challenges/weekly", headers=h, timeout=30)
        active_id = r.json()["challenge"]["id"]
        week_key = _current_week_key()

        # backup demo1 user state
        u_before = db.users.find_one({"id": user_id}) or {}
        xp_before = u_before.get("xp", 0)
        streak_before = u_before.get("streak_weeks", 0)
        last_week_before = u_before.get("last_streak_week")
        badges_before = u_before.get("challenge_badges", [])

        # ensure no prior completion this week
        db.challenge_completions.delete_many({"user_id": user_id, "challenge_id": active_id, "week_key": week_key})
        # reset xp/streak so awards are predictable
        db.users.update_one({"id": user_id}, {"$set": {"xp": 0, "streak_weeks": 0, "last_streak_week": None, "challenge_badges": []}})

        try:
            # 1st call awards XP
            r1 = requests.post(f"{BASE_URL}/api/challenges/{active_id}/complete", headers=h, timeout=30)
            assert r1.status_code == 200, r1.text
            d1 = r1.json()
            assert d1.get("completed") is True
            assert d1.get("xp_awarded") > 0
            xp_after = d1["xp"]
            # 2nd call → already_completed
            r2 = requests.post(f"{BASE_URL}/api/challenges/{active_id}/complete", headers=h, timeout=30)
            assert r2.status_code == 200
            d2 = r2.json()
            assert d2.get("already_completed") is True
            assert d2.get("xp") == xp_after  # no double XP
        finally:
            db.challenge_completions.delete_many({"user_id": user_id, "challenge_id": active_id, "week_key": week_key})
            db.users.update_one(
                {"id": user_id},
                {"$set": {
                    "xp": xp_before,
                    "streak_weeks": streak_before,
                    "last_streak_week": last_week_before,
                    "challenge_badges": badges_before,
                }}
            )

    def test_leaderboard_shape(self, demo1_headers):
        h, _ = demo1_headers
        r = requests.get(f"{BASE_URL}/api/challenges/leaderboard", headers=h, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "leaderboard" in d
        assert isinstance(d["leaderboard"], list)
        assert len(d["leaderboard"]) <= 10
        assert "my_rank" in d
        assert "my_xp" in d
        for row in d["leaderboard"]:
            for k in ("id", "name", "xp", "streak_weeks", "badges_count"):
                assert k in row

    def test_history_returns_completions_with_title(self, demo1_headers):
        h, user_id = demo1_headers
        # ensure at least one completion (we keep it temporarily)
        r0 = requests.get(f"{BASE_URL}/api/challenges/weekly", headers=h, timeout=30)
        active_id = r0.json()["challenge"]["id"]
        week_key = _current_week_key()
        # snapshot
        u_before = db.users.find_one({"id": user_id}) or {}
        backup = {k: u_before.get(k) for k in ("xp", "streak_weeks", "last_streak_week", "challenge_badges")}
        had = db.challenge_completions.find_one({"user_id": user_id, "challenge_id": active_id, "week_key": week_key})
        try:
            if not had:
                requests.post(f"{BASE_URL}/api/challenges/{active_id}/complete", headers=h, timeout=30)
            r = requests.get(f"{BASE_URL}/api/challenges/history", headers=h, timeout=30)
            assert r.status_code == 200, r.text
            items = r.json()["completions"]
            assert isinstance(items, list)
            assert len(items) <= 50
            assert len(items) >= 1
            for it in items:
                assert "challenge_id" in it
                assert "title" in it, f"title missing from history item: {it}"
        finally:
            if not had:
                db.challenge_completions.delete_one({"user_id": user_id, "challenge_id": active_id, "week_key": week_key})
            db.users.update_one({"id": user_id}, {"$set": backup})


# =========================================================
# Streak edge cases
# =========================================================
class TestStreak:
    def _setup_state(self, user_id, last_streak_week, streak_weeks, xp=0):
        db.users.update_one({"id": user_id}, {"$set": {
            "xp": xp,
            "streak_weeks": streak_weeks,
            "last_streak_week": last_streak_week,
            "challenge_badges": [],
        }})

    def _cleanup(self, user_id, active_id, week_key, backup):
        db.challenge_completions.delete_many({"user_id": user_id, "challenge_id": active_id, "week_key": week_key})
        db.users.update_one({"id": user_id}, {"$set": backup})

    def _backup(self, user_id):
        u = db.users.find_one({"id": user_id}) or {}
        return {k: u.get(k) for k in ("xp", "streak_weeks", "last_streak_week", "challenge_badges")}

    def test_streak_resets_to_one_if_skipped(self, demo1_headers):
        h, user_id = demo1_headers
        r0 = requests.get(f"{BASE_URL}/api/challenges/weekly", headers=h, timeout=30)
        active_id = r0.json()["challenge"]["id"]
        week_key = _current_week_key()
        backup = self._backup(user_id)
        try:
            db.challenge_completions.delete_many({"user_id": user_id, "challenge_id": active_id, "week_key": week_key})
            # Set last_streak_week to 2 weeks ago + streak_weeks=5 — user skipped a week
            self._setup_state(user_id, _two_weeks_ago_key(), 5)
            r = requests.post(f"{BASE_URL}/api/challenges/{active_id}/complete", headers=h, timeout=30)
            assert r.status_code == 200, r.text
            d = r.json()
            assert d["streak_weeks"] == 1, f"expected streak=1 after skip, got {d['streak_weeks']}"
        finally:
            self._cleanup(user_id, active_id, week_key, backup)

    def test_streak_increments_if_completed_last_week(self, demo1_headers):
        h, user_id = demo1_headers
        r0 = requests.get(f"{BASE_URL}/api/challenges/weekly", headers=h, timeout=30)
        active_id = r0.json()["challenge"]["id"]
        week_key = _current_week_key()
        backup = self._backup(user_id)
        try:
            db.challenge_completions.delete_many({"user_id": user_id, "challenge_id": active_id, "week_key": week_key})
            # Set last_streak_week = last week, streak=3 — continuation case
            self._setup_state(user_id, _last_week_key(), 3)
            r = requests.post(f"{BASE_URL}/api/challenges/{active_id}/complete", headers=h, timeout=30)
            assert r.status_code == 200, r.text
            d = r.json()
            assert d["streak_weeks"] == 4, f"expected streak=4 after continuation, got {d['streak_weeks']}"
        finally:
            self._cleanup(user_id, active_id, week_key, backup)


# =========================================================
# Level / XP math via API
# =========================================================
class TestLevelMath:
    """We test _xp_to_level boundaries indirectly via /api/challenges/weekly after
    setting xp directly in the DB. levels list = [0,100,200,300,400,500,...]
    100 → level 1, 200 → 2, 400 → 4, 500 → 5."""

    @pytest.mark.parametrize("xp,expected_level", [
        (0, 0),
        (100, 1),
        (200, 2),
        (400, 4),
        (500, 5),
        (99, 0),
        (1500, 10),
    ])
    def test_xp_boundary(self, demo1_headers, xp, expected_level):
        h, user_id = demo1_headers
        u = db.users.find_one({"id": user_id}) or {}
        backup_xp = u.get("xp", 0)
        try:
            db.users.update_one({"id": user_id}, {"$set": {"xp": xp}})
            r = requests.get(f"{BASE_URL}/api/challenges/weekly", headers=h, timeout=30)
            assert r.status_code == 200
            d = r.json()
            assert d["level_info"]["level"] == expected_level, f"xp={xp} → level expected {expected_level} got {d['level_info']['level']}"
            assert d["level_info"]["xp_current"] == xp
        finally:
            db.users.update_one({"id": user_id}, {"$set": {"xp": backup_xp}})

    def test_rising_spark_badge_at_level_5(self, demo1_headers):
        """Setting XP to 400 then completing a 100-XP challenge → new_xp=500 → level=5 → 'Rising Spark' badge."""
        h, user_id = demo1_headers
        r0 = requests.get(f"{BASE_URL}/api/challenges/weekly", headers=h, timeout=30)
        active = r0.json()["challenge"]
        active_id = active["id"]
        active_xp = active["xp"]
        week_key = _current_week_key()
        u = db.users.find_one({"id": user_id}) or {}
        backup = {k: u.get(k) for k in ("xp", "streak_weeks", "last_streak_week", "challenge_badges")}
        try:
            db.challenge_completions.delete_many({"user_id": user_id, "challenge_id": active_id, "week_key": week_key})
            # Set xp so that completing active gives level >= 5
            target_pre = max(0, 500 - active_xp)
            db.users.update_one({"id": user_id}, {"$set": {
                "xp": target_pre, "streak_weeks": 0, "last_streak_week": None, "challenge_badges": []
            }})
            r = requests.post(f"{BASE_URL}/api/challenges/{active_id}/complete", headers=h, timeout=30)
            assert r.status_code == 200, r.text
            d = r.json()
            assert d["level_info"]["level"] >= 5
            # Verify badge in DB
            u_now = db.users.find_one({"id": user_id}) or {}
            assert "Rising Spark" in (u_now.get("challenge_badges") or []), f"Rising Spark badge missing, got {u_now.get('challenge_badges')}"
            assert "Rising Spark" in d.get("new_badges", [])
        finally:
            db.challenge_completions.delete_many({"user_id": user_id, "challenge_id": active_id, "week_key": week_key})
            db.users.update_one({"id": user_id}, {"$set": backup})
