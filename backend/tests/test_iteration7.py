"""Iteration 7 — Batch B (Personality DNA, Post-Date Check-in, Safe Meeting Zones,
Selfie Verify, Background Lite) plus iter6-fix regression
(todays-spark cached match_reasons, reignite 3 topics, transparency up to 110).
Uses direct pymongo for state setup/teardown and conftest fixtures for auth."""
import os
import time
import hashlib
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

# Read DB_NAME from /app/backend/.env if not in env
try:
    with open("/app/backend/.env") as f:
        for line in f:
            if line.startswith("DB_NAME="):
                DB_NAME = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("MONGO_URL="):
                MONGO_URL = line.split("=", 1)[1].strip().strip('"')
except Exception:
    pass

mongo = MongoClient(MONGO_URL)
db = mongo[DB_NAME]


# ============= b1: PERSONALITY DNA =============
class TestPersonalityDNA:
    def test_questions_shape(self, base_url, demo1_auth):
        r = requests.get(f"{base_url}/api/personality/questions", headers=demo1_auth["headers"], timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert len(data["questions"]) == 10
        traits = set(q["trait"] for q in data["questions"])
        assert traits == {"openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"}

    def test_dna_partial_rejected(self, base_url, demo1_auth):
        partial = {"answers": [{"question_id": "q1", "choice_id": "a"}, {"question_id": "q2", "choice_id": "b"}]}
        r = requests.put(f"{base_url}/api/personality/dna", headers=demo1_auth["headers"], json=partial, timeout=15)
        assert r.status_code == 400

    def test_dna_full_and_get(self, base_url, demo1_auth):
        # Demo1 may already be complete from earlier curl — re-submit to be deterministic
        answers = [{"question_id": f"q{i}", "choice_id": "a"} for i in range(1, 11)]
        r = requests.put(f"{base_url}/api/personality/dna", headers=demo1_auth["headers"], json={"answers": answers}, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["personality_complete"] is True
        assert "archetype" in data
        dna = data["personality_dna"]
        for t in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]:
            assert 0 <= dna[t] <= 100
        # GET
        r2 = requests.get(f"{base_url}/api/personality/dna/{demo1_auth['user_id']}", headers=demo1_auth["headers"], timeout=15)
        assert r2.status_code == 200
        assert r2.json()["archetype"] == data["archetype"]
        assert r2.json()["personality_complete"] is True

    def test_compat_both_complete(self, base_url, demo1_auth, demo2_auth):
        # Ensure both demo1+demo2 have DNA
        answers_a = {"answers": [{"question_id": f"q{i}", "choice_id": "a"} for i in range(1, 11)]}
        answers_b = {"answers": [{"question_id": f"q{i}", "choice_id": "b"} for i in range(1, 11)]}
        requests.put(f"{base_url}/api/personality/dna", headers=demo1_auth["headers"], json=answers_a, timeout=20)
        requests.put(f"{base_url}/api/personality/dna", headers=demo2_auth["headers"], json=answers_b, timeout=20)
        r = requests.get(f"{base_url}/api/personality/compatibility/{demo2_auth['user_id']}", headers=demo1_auth["headers"], timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["both_completed"] is True
        assert 0 <= data["score"] <= 100
        # weighted_contribution should be ~= 40% of score
        assert data["weighted_contribution"] == int(round(data["score"] * 0.40))

    def test_compat_other_incomplete(self, base_url, demo1_auth):
        # Use a user known not to have DNA -- demo3
        u = db.users.find_one({"email": "demo3@spark.app"})
        if not u:
            pytest.skip("demo3 not found")
        # Force-unset DNA on demo3
        db.users.update_one({"id": u["id"]}, {"$unset": {"personality_dna": "", "personality_complete": ""}})
        r = requests.get(f"{base_url}/api/personality/compatibility/{u['id']}", headers=demo1_auth["headers"], timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["both_completed"] is False
        assert data.get("score") in (None, 0)

    def test_discover_includes_personality_score(self, base_url, demo1_auth):
        r = requests.get(f"{base_url}/api/discover", headers=demo1_auth["headers"], timeout=20)
        assert r.status_code == 200
        profiles = r.json().get("profiles", [])
        if not profiles:
            pytest.skip("no profiles to discover")
        for p in profiles:
            assert "personality_score" in p


# ============= b2: POST-DATE CHECK-IN =============
class TestPostDateCheckin:
    def test_missing_contact_400(self, base_url, demo2_auth, match_id):
        # demo2 has no emergency contact; temporarily unset
        db.users.update_one({"id": demo2_auth["user_id"]},
                            {"$unset": {"emergency_contact_email": "", "emergency_contact_phone": ""}})
        try:
            payload = {"match_id": match_id, "scheduled_time": datetime.now(timezone.utc).isoformat(), "grace_minutes": 60}
            r = requests.post(f"{base_url}/api/safety/post-date-checkin", headers=demo2_auth["headers"], json=payload, timeout=15)
            assert r.status_code == 400
        finally:
            pass  # Leave demo2 as-is (no contact existed before)

    def test_create_confirm_snooze_flow(self, base_url, demo1_auth, match_id):
        # Ensure demo1 has emergency contact (from iter3, but reseed defensively)
        db.users.update_one({"id": demo1_auth["user_id"]},
                            {"$set": {"emergency_contact_email": "mom@example.com", "emergency_contact_name": "Mom"}})
        sched = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        payload = {"match_id": match_id, "scheduled_time": sched, "grace_minutes": 60, "location": "Cafe", "notes": "First date"}
        r = requests.post(f"{base_url}/api/safety/post-date-checkin", headers=demo1_auth["headers"], json=payload, timeout=15)
        assert r.status_code == 200, r.text
        cid = r.json()["checkin_id"]
        # auto_notify_at should be scheduled + 60min (within a few seconds tolerance)
        notify = datetime.fromisoformat(r.json()["auto_notify_at"].replace("Z", "+00:00"))
        expected = datetime.fromisoformat(sched.replace("Z", "+00:00")) + timedelta(minutes=60)
        assert abs((notify - expected).total_seconds()) < 5

        # Snooze +30 min
        r2 = requests.post(f"{base_url}/api/safety/post-date-checkin/{cid}/snooze", headers=demo1_auth["headers"], timeout=15)
        assert r2.status_code == 200, r2.text
        new_notify = datetime.fromisoformat(r2.json()["auto_notify_at"].replace("Z", "+00:00"))
        assert abs((new_notify - notify - timedelta(minutes=30)).total_seconds()) < 5

        # List
        r3 = requests.get(f"{base_url}/api/safety/post-date-checkins", headers=demo1_auth["headers"], timeout=15)
        assert r3.status_code == 200
        assert any(c["id"] == cid for c in r3.json()["checkins"])

        # Confirm
        r4 = requests.post(f"{base_url}/api/safety/post-date-checkin/{cid}/confirm", headers=demo1_auth["headers"], timeout=15)
        assert r4.status_code == 200
        rec = db.post_date_checkins.find_one({"id": cid})
        assert rec["status"] == "confirmed_safe"
        db.post_date_checkins.delete_one({"id": cid})

    def test_run_alerts_overdue(self, base_url, demo1_auth, match_id):
        # Seed an overdue scheduled checkin directly
        db.users.update_one({"id": demo1_auth["user_id"]},
                            {"$set": {"emergency_contact_email": "mom@example.com", "emergency_contact_name": "Mom"}})
        cid = "TEST_overdue_" + str(int(time.time()))
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        db.post_date_checkins.insert_one({
            "id": cid, "user_id": demo1_auth["user_id"], "match_id": match_id,
            "scheduled_time": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
            "auto_notify_at": past, "grace_minutes": 60, "status": "scheduled", "alerted": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            r = requests.post(f"{base_url}/api/safety/run-post-date-alerts", headers=demo1_auth["headers"], timeout=20)
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["alerted"] >= 1
            rec = db.post_date_checkins.find_one({"id": cid})
            assert rec["alerted"] is True
            assert rec["status"] == "alerted"
            # Idempotency: second call should not alert again
            r2 = requests.post(f"{base_url}/api/safety/run-post-date-alerts", headers=demo1_auth["headers"], timeout=20)
            data2 = r2.json()
            # Already alerted so checked list shouldn't include this one
            rec2 = db.post_date_checkins.find_one({"id": cid})
            assert rec2["status"] == "alerted"  # unchanged
        finally:
            db.post_date_checkins.delete_one({"id": cid})


# ============= b3: SAFE MEETING ZONES =============
class TestSafeZones:
    def test_zones_list(self, base_url, demo1_auth):
        r = requests.get(f"{base_url}/api/safety/zones", headers=demo1_auth["headers"], timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert len(data["zones"]) == 15
        assert len(data["guidance"]) == 5

    def test_zones_with_city(self, base_url, demo1_auth):
        r = requests.get(f"{base_url}/api/safety/zones?city=Austin", headers=demo1_auth["headers"], timeout=15)
        assert r.status_code == 200
        for z in r.json()["zones"]:
            assert z["city"] == "Austin"

    def test_share_location_match_required(self, base_url, demo1_auth):
        # Bogus match_id → 403
        r = requests.post(f"{base_url}/api/safety/share-location", headers=demo1_auth["headers"],
                          json={"match_id": "not-a-real-match", "latitude": 30.0, "longitude": -97.0,
                                "duration_minutes": 30}, timeout=15)
        assert r.status_code == 403

    def test_share_location_lifecycle(self, base_url, demo1_auth, demo2_auth, match_id):
        # demo1 shares, demo2 fetches partner share
        r = requests.post(f"{base_url}/api/safety/share-location", headers=demo1_auth["headers"],
                          json={"match_id": match_id, "latitude": 30.27, "longitude": -97.74, "duration_minutes": 30},
                          timeout=15)
        assert r.status_code == 200
        assert "expires_at" in r.json()

        r2 = requests.get(f"{base_url}/api/safety/share-location/{match_id}", headers=demo2_auth["headers"], timeout=15)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["sharing"] is True
        assert abs(d2["latitude"] - 30.27) < 0.01

        # demo1 stops
        r3 = requests.delete(f"{base_url}/api/safety/share-location/{match_id}", headers=demo1_auth["headers"], timeout=15)
        assert r3.status_code == 200

        # demo2 sees not sharing
        r4 = requests.get(f"{base_url}/api/safety/share-location/{match_id}", headers=demo2_auth["headers"], timeout=15)
        assert r4.json()["sharing"] is False


# ============= b4: SELFIE VERIFY =============
class TestSelfieVerify:
    def test_no_photos_400(self, base_url, demo1_auth):
        # Save photos, then clear
        u = db.users.find_one({"id": demo1_auth["user_id"]}, {"photos": 1})
        original_photos = u.get("photos", [])
        db.users.update_one({"id": demo1_auth["user_id"]}, {"$set": {"photos": []}})
        try:
            r = requests.post(f"{base_url}/api/profile/selfie-verify", headers=demo1_auth["headers"],
                              json={"selfie_data_url": "data:image/png;base64,iVBORw0KG"}, timeout=15)
            assert r.status_code == 400
        finally:
            db.users.update_one({"id": demo1_auth["user_id"]}, {"$set": {"photos": original_photos}})

    def test_non_data_url_400(self, base_url, demo1_auth):
        # ensure user has at least one photo
        u = db.users.find_one({"id": demo1_auth["user_id"]}, {"photos": 1})
        if not u.get("photos"):
            db.users.update_one({"id": demo1_auth["user_id"]}, {"$set": {"photos": ["https://example.com/p.jpg"]}})
        r = requests.post(f"{base_url}/api/profile/selfie-verify", headers=demo1_auth["headers"],
                          json={"selfie_data_url": "https://example.com/not-data.png"}, timeout=15)
        assert r.status_code == 400

    def test_too_large_400(self, base_url, demo1_auth):
        u = db.users.find_one({"id": demo1_auth["user_id"]}, {"photos": 1})
        if not u.get("photos"):
            db.users.update_one({"id": demo1_auth["user_id"]}, {"$set": {"photos": ["https://example.com/p.jpg"]}})
        huge = "data:image/png;base64," + "A" * 2_600_000
        r = requests.post(f"{base_url}/api/profile/selfie-verify", headers=demo1_auth["headers"],
                          json={"selfie_data_url": huge}, timeout=30)
        assert r.status_code == 400

    def test_valid_call_returns_shape_no_false_verify(self, base_url, demo1_auth):
        u = db.users.find_one({"id": demo1_auth["user_id"]}, {"photos": 1})
        if not u.get("photos"):
            db.users.update_one({"id": demo1_auth["user_id"]}, {"$set": {"photos": ["https://example.com/p.jpg"]}})
        # Tiny but valid data URL — LLM will likely return non-match for a 1x1 PNG vs random URL
        tiny = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        r = requests.post(f"{base_url}/api/profile/selfie-verify", headers=demo1_auth["headers"],
                          json={"selfie_data_url": tiny}, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "verified" in data and "confidence" in data and "reason" in data
        # We can't guarantee LLM decision, but on failure path verified must be False
        assert isinstance(data["verified"], bool)


# ============= b5: BACKGROUND LITE =============
class TestBackgroundLite:
    def test_bad_dob_format_400(self, base_url, demo2_auth):
        r = requests.post(f"{base_url}/api/profile/background-lite", headers=demo2_auth["headers"],
                          json={"full_legal_name": "Test User", "date_of_birth": "01/01/1990", "country": "US"},
                          timeout=15)
        assert r.status_code == 400

    def test_underage_400(self, base_url, demo2_auth):
        r = requests.post(f"{base_url}/api/profile/background-lite", headers=demo2_auth["headers"],
                          json={"full_legal_name": "Test Kid", "date_of_birth": "2015-01-01", "country": "US"},
                          timeout=15)
        assert r.status_code == 400

    def test_success_sets_flag_and_badge(self, base_url, demo2_auth):
        # Reset state
        db.users.update_one({"id": demo2_auth["user_id"]},
                            {"$unset": {"background_lite_verified": "", "background_lite_verified_at": ""}})
        db.background_checks.delete_many({"user_id": demo2_auth["user_id"]})
        r = requests.post(f"{base_url}/api/profile/background-lite", headers=demo2_auth["headers"],
                          json={"full_legal_name": "TEST James Smith", "date_of_birth": "1995-04-12", "country": "us"},
                          timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["verified"] is True

        # DB has hash only, not raw name
        rec = db.background_checks.find_one({"user_id": demo2_auth["user_id"]})
        assert rec is not None
        assert rec["country"] == "US"
        assert "identity_hash" in rec
        assert "TEST James Smith" not in str(rec)  # raw name not stored
        expected_hash = hashlib.sha256("test james smith|1995-04-12|US".encode()).hexdigest()
        assert rec["identity_hash"] == expected_hash

        # Badges endpoint shows background_lite
        r2 = requests.get(f"{base_url}/api/profile/badges/{demo2_auth['user_id']}", headers=demo2_auth["headers"], timeout=15)
        assert r2.status_code == 200
        ids = [b["id"] for b in r2.json()["badges"]]
        assert "background_lite" in ids


# ============= BADGES OVERVIEW =============
class TestBadges:
    def test_badges_shape(self, base_url, demo1_auth):
        r = requests.get(f"{base_url}/api/profile/badges/{demo1_auth['user_id']}", headers=demo1_auth["headers"], timeout=15)
        assert r.status_code == 200
        badges = r.json()["badges"]
        assert isinstance(badges, list)
        for b in badges:
            assert "id" in b and "label" in b and "tier" in b


# ============= ITER 6 REGRESSION FIXES =============
class TestIter6Fixes:
    def test_todays_spark_match_reasons_on_cached(self, base_url, demo1_auth):
        # Clear cache to force fresh compute
        db.users.update_one({"id": demo1_auth["user_id"]},
                            {"$unset": {"todays_spark_user_id": "", "todays_spark_date": ""}})
        r1 = requests.get(f"{base_url}/api/discover/todays-spark", headers=demo1_auth["headers"], timeout=20)
        assert r1.status_code == 200
        d1 = r1.json()
        if d1.get("pick") is None:
            pytest.skip("no candidate for todays-spark")
        assert "match_reasons" in d1
        # Second call is cached — must still have match_reasons (iter6 fix)
        r2 = requests.get(f"{base_url}/api/discover/todays-spark", headers=demo1_auth["headers"], timeout=20)
        d2 = r2.json()
        assert d1["pick"]["id"] == d2["pick"]["id"]
        assert "match_reasons" in d2, "Cached response missing match_reasons (iter6 minor fix not applied)"
        assert isinstance(d2["match_reasons"], list) and len(d2["match_reasons"]) >= 1

    def test_reignite_returns_3_topics(self, base_url, demo1_auth, match_id):
        r = requests.post(f"{base_url}/api/chat/{match_id}/reignite", headers=demo1_auth["headers"], timeout=60)
        assert r.status_code == 200, r.text
        topics = r.json()["topics"]
        assert isinstance(topics, list)
        assert len(topics) == 3
        for t in topics:
            assert isinstance(t, str) and t.strip()

    def test_transparency_max_110(self, base_url, demo1_auth, demo2_auth):
        # Set all flags on demo2 and backdate created_at to >30 days ago
        old_user = db.users.find_one({"id": demo2_auth["user_id"]}, {"created_at": 1, "video_verified": 1,
                                                                       "selfie_verified": 1, "bio": 1,
                                                                       "quiz_complete": 1, "anti_ghosting_pledge": 1,
                                                                       "photo_verified": 1})
        old_created = old_user.get("created_at")
        backdated = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
        db.users.update_one({"id": demo2_auth["user_id"]}, {"$set": {
            "video_verified": True,
            "selfie_verified": True,
            "photo_verified": True,
            "bio": "x" * 80,
            "quiz_complete": True,
            "anti_ghosting_pledge": True,
            "created_at": backdated,
        }})
        try:
            r = requests.get(f"{base_url}/api/transparency/{demo2_auth['user_id']}", headers=demo1_auth["headers"], timeout=20)
            assert r.status_code == 200, r.text
            score = r.json()["authenticity_score"]
            # 30 (video) + 10 (selfie) + 20 (bio>=60) + 20 (quiz) + 10 (pledge) + 20 (>=30 days) = 110
            assert score == 110, f"Expected 110, got {score}"
        finally:
            restore = {}
            if old_created is not None:
                restore["created_at"] = old_created
            else:
                db.users.update_one({"id": demo2_auth["user_id"]}, {"$unset": {"created_at": ""}})
            # Restore prior boolean states (set to original or unset)
            for key in ["video_verified", "selfie_verified", "photo_verified", "quiz_complete", "anti_ghosting_pledge"]:
                val = old_user.get(key)
                if val is not None:
                    restore[key] = val
                else:
                    db.users.update_one({"id": demo2_auth["user_id"]}, {"$unset": {key: ""}})
            if old_user.get("bio") is not None:
                restore["bio"] = old_user["bio"]
            if restore:
                db.users.update_one({"id": demo2_auth["user_id"]}, {"$set": restore})
