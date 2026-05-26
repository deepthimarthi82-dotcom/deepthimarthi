"""Iteration 11 — Advanced Filters tests.

Covers:
- UserProfile new optional fields round-trip via PUT/GET /api/profile
- /api/options/profile-fields contains filter_options with 11 keys
- GET /api/me/filters returns {filters, is_premium, advanced_keys (15), free_keys (4)}
- PUT /api/me/filters as FREE user persists only base filters
- PUT /api/me/filters as PREMIUM user persists all advanced filters
- Validation rules: age_min>age_max -> 400, height range -> 400, clamps
- DELETE /api/me/filters
- /api/discover filter application (age, recently_active_only)
- Empty list filters stripped
"""
import os
import time
from datetime import datetime, timezone, timedelta

import pytest
import requests
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

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
# Read from backend/.env as backup
try:
    with open("/app/backend/.env") as f:
        for line in f:
            if line.startswith("MONGO_URL=") and not MONGO_URL.startswith("mongodb"):
                MONGO_URL = line.split("=", 1)[1].strip().strip('"')
            if line.startswith("DB_NAME="):
                DB_NAME = line.split("=", 1)[1].strip().strip('"')
except Exception:
    pass

DEMO1 = {"email": "demo1@spark.app", "password": "password123"}
DEMO2 = {"email": "demo2@spark.app", "password": "password123"}
PREMIUM = {"email": "deepthimarthi82@gmail.com", "password": "Spark2026!"}

EXPECTED_FILTER_OPTION_KEYS = {
    "education", "body_type", "drinking", "smoking", "cannabis",
    "religion", "politics", "has_kids", "wants_kids", "exercise", "pets",
}
EXPECTED_FREE_KEYS = {"age_min", "age_max", "distance_max", "recently_active_only"}
EXPECTED_ADVANCED_KEYS_COUNT = 15  # 11 list keys + height_min + height_max + must_be_verified + must_have_personality_dna


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #
def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed for {creds['email']}: {r.status_code} {r.text[:200]}")
    d = r.json()
    return {"token": d["token"], "user_id": d["user_id"], "headers": {"Authorization": f"Bearer {d['token']}"}}


@pytest.fixture(scope="module")
def demo1_auth():
    return _login(DEMO1)


@pytest.fixture(scope="module")
def demo2_auth():
    return _login(DEMO2)


@pytest.fixture(scope="module")
def premium_auth():
    return _login(PREMIUM)


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(autouse=True)
def _cleanup_demo1_filters(demo1_auth):
    """Ensure demo1 starts with no filters and is restored at end."""
    requests.delete(f"{BASE_URL}/api/me/filters", headers=demo1_auth["headers"], timeout=15)
    yield
    requests.delete(f"{BASE_URL}/api/me/filters", headers=demo1_auth["headers"], timeout=15)


# --------------------------------------------------------------------------- #
# 1. UserProfile new fields round-trip                                        #
# --------------------------------------------------------------------------- #
class TestProfileFieldsRoundTrip:
    def test_profile_new_fields_persist(self, demo1_auth):
        # Get current profile so we can preserve required fields
        me = requests.get(f"{BASE_URL}/api/auth/me", headers=demo1_auth["headers"], timeout=15)
        assert me.status_code == 200, me.text
        meu = me.json()
        payload = {
            "name": meu.get("name", "Emma"),
            "age": meu.get("age") or 28,
            "gender": meu.get("gender") or "woman",
            "looking_for": meu.get("looking_for") or "men",
            "bio": meu.get("bio") or "test",
            "photos": meu.get("photos") or [],
            "height_cm": 170,
            "body_type": "athletic",
            "drinking": "socially",
            "smoking": "never",
            "cannabis": "never",
            "religion": "spiritual",
            "politics": "center",
            "has_kids": "no",
            "wants_kids": "maybe",
            "exercise": "weekly",
            "pets": ["dog", "cat"],
        }
        r = requests.put(f"{BASE_URL}/api/profile", json=payload, headers=demo1_auth["headers"], timeout=20)
        assert r.status_code == 200, r.text

        g = requests.get(f"{BASE_URL}/api/profile/{demo1_auth['user_id']}", headers=demo1_auth["headers"], timeout=15)
        assert g.status_code == 200, g.text
        gp = g.json()
        assert gp["height_cm"] == 170
        assert gp["body_type"] == "athletic"
        assert gp["drinking"] == "socially"
        assert gp["smoking"] == "never"
        assert gp["cannabis"] == "never"
        assert gp["religion"] == "spiritual"
        assert gp["politics"] == "center"
        assert gp["has_kids"] == "no"
        assert gp["wants_kids"] == "maybe"
        assert gp["exercise"] == "weekly"
        assert sorted(gp["pets"]) == ["cat", "dog"]


# --------------------------------------------------------------------------- #
# 2. /api/options/profile-fields filter_options                               #
# --------------------------------------------------------------------------- #
class TestProfileFieldOptions:
    def test_filter_options_keys_and_shape(self):
        r = requests.get(f"{BASE_URL}/api/options/profile-fields", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "filter_options" in data
        fo = data["filter_options"]
        keys = set(fo.keys())
        assert keys == EXPECTED_FILTER_OPTION_KEYS, f"unexpected keys: extra={keys - EXPECTED_FILTER_OPTION_KEYS}, missing={EXPECTED_FILTER_OPTION_KEYS - keys}"
        for k, arr in fo.items():
            assert isinstance(arr, list) and len(arr) > 0, f"{k} should be non-empty list"
            for item in arr:
                assert isinstance(item, dict)
                assert "value" in item and "label" in item, f"{k} item missing value/label: {item}"
                assert isinstance(item["value"], str) and isinstance(item["label"], str)


# --------------------------------------------------------------------------- #
# 3. GET /api/me/filters                                                      #
# --------------------------------------------------------------------------- #
class TestGetFilters:
    def test_get_filters_shape_free(self, demo1_auth):
        r = requests.get(f"{BASE_URL}/api/me/filters", headers=demo1_auth["headers"], timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "filters" in d and isinstance(d["filters"], dict)
        assert d["is_premium"] is False
        assert set(d["free_keys"]) == EXPECTED_FREE_KEYS
        assert len(d["advanced_keys"]) == EXPECTED_ADVANCED_KEYS_COUNT
        for needed in ["height_cm_min", "height_cm_max", "must_be_verified", "must_have_personality_dna",
                       "education", "body_type", "drinking", "smoking", "cannabis", "religion",
                       "politics", "has_kids", "wants_kids", "exercise", "pets"]:
            assert needed in d["advanced_keys"], f"{needed} missing from advanced_keys"

    def test_get_filters_premium_flag(self, premium_auth):
        r = requests.get(f"{BASE_URL}/api/me/filters", headers=premium_auth["headers"], timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["is_premium"] is True


# --------------------------------------------------------------------------- #
# 4. PUT /api/me/filters FREE                                                 #
# --------------------------------------------------------------------------- #
class TestPutFiltersFree:
    def test_free_user_drops_premium_fields(self, demo1_auth, mongo):
        payload = {
            "age_min": 25, "age_max": 40,
            "distance_max": 50, "recently_active_only": True,
            # premium-only — should be dropped silently
            "height_cm_min": 160, "height_cm_max": 190,
            "education": ["bachelor", "master"],
            "body_type": ["athletic"],
            "drinking": ["socially"],
            "must_be_verified": True,
            "must_have_personality_dna": True,
        }
        r = requests.put(f"{BASE_URL}/api/me/filters", json=payload, headers=demo1_auth["headers"], timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["is_premium"] is False
        saved = body["filters"]
        assert set(saved.keys()) == EXPECTED_FREE_KEYS
        assert saved["age_min"] == 25 and saved["age_max"] == 40
        assert saved["distance_max"] == 50 and saved["recently_active_only"] is True

        # DB verification
        u = mongo.users.find_one({"id": demo1_auth["user_id"]}, {"_id": 0, "filters": 1})
        assert u and "filters" in u
        assert set(u["filters"].keys()) == EXPECTED_FREE_KEYS
        assert "education" not in u["filters"]
        assert "must_be_verified" not in u["filters"]

        # GET round-trip
        g = requests.get(f"{BASE_URL}/api/me/filters", headers=demo1_auth["headers"], timeout=15)
        assert g.status_code == 200
        assert set(g.json()["filters"].keys()) == EXPECTED_FREE_KEYS

    def test_empty_list_filters_stripped(self, demo1_auth, mongo):
        payload = {"age_min": 22, "body_type": [], "education": [], "pets": []}
        r = requests.put(f"{BASE_URL}/api/me/filters", json=payload, headers=demo1_auth["headers"], timeout=15)
        assert r.status_code == 200, r.text
        saved = r.json()["filters"]
        for k in ("body_type", "education", "pets"):
            assert k not in saved, f"{k}=[] should be stripped"
        # DB
        u = mongo.users.find_one({"id": demo1_auth["user_id"]}, {"_id": 0, "filters": 1})
        for k in ("body_type", "education", "pets"):
            assert k not in (u.get("filters") or {}), f"{k} unexpectedly persisted"


# --------------------------------------------------------------------------- #
# 5. PUT /api/me/filters PREMIUM                                              #
# --------------------------------------------------------------------------- #
class TestPutFiltersPremium:
    def test_premium_persists_all(self, premium_auth, mongo):
        payload = {
            "age_min": 25, "age_max": 45,
            "distance_max": 100, "recently_active_only": False,
            "height_cm_min": 160, "height_cm_max": 190,
            "education": ["bachelor", "master"],
            "body_type": ["athletic"],
            "drinking": ["socially", "rarely"],
            "smoking": ["never"],
            "cannabis": ["never"],
            "religion": ["spiritual", "agnostic"],
            "politics": ["center"],
            "has_kids": ["no"],
            "wants_kids": ["yes", "maybe"],
            "exercise": ["weekly", "daily"],
            "pets": ["dog"],
            "must_be_verified": True,
            "must_have_personality_dna": False,
        }
        r = requests.put(f"{BASE_URL}/api/me/filters", json=payload, headers=premium_auth["headers"], timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["is_premium"] is True
        saved = body["filters"]
        assert saved["height_cm_min"] == 160 and saved["height_cm_max"] == 190
        assert sorted(saved["education"]) == ["bachelor", "master"]
        assert saved["must_be_verified"] is True
        # must_have_personality_dna False is `exclude_none` — False is not None so should persist
        assert saved.get("must_have_personality_dna") is False
        # DB
        u = mongo.users.find_one({"id": premium_auth["user_id"]}, {"_id": 0, "filters": 1})
        f = u["filters"]
        assert sorted(f["education"]) == ["bachelor", "master"]
        assert f["height_cm_min"] == 160

    def test_premium_cleanup(self, premium_auth):
        # Clear premium user filters so subsequent suites are unaffected
        r = requests.delete(f"{BASE_URL}/api/me/filters", headers=premium_auth["headers"], timeout=15)
        assert r.status_code == 200


# --------------------------------------------------------------------------- #
# 6. Validation + clamping                                                    #
# --------------------------------------------------------------------------- #
class TestFilterValidation:
    def test_age_min_greater_than_max_400(self, demo1_auth):
        r = requests.put(f"{BASE_URL}/api/me/filters",
                         json={"age_min": 50, "age_max": 30},
                         headers=demo1_auth["headers"], timeout=15)
        assert r.status_code == 400, r.text

    def test_height_min_greater_than_max_400(self, premium_auth):
        r = requests.put(f"{BASE_URL}/api/me/filters",
                         json={"height_cm_min": 200, "height_cm_max": 150},
                         headers=premium_auth["headers"], timeout=15)
        assert r.status_code == 400, r.text
        # cleanup
        requests.delete(f"{BASE_URL}/api/me/filters", headers=premium_auth["headers"], timeout=15)

    def test_age_min_clamps_to_18(self, demo1_auth):
        r = requests.put(f"{BASE_URL}/api/me/filters",
                         json={"age_min": 12, "age_max": 30},
                         headers=demo1_auth["headers"], timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["filters"]["age_min"] == 18

    def test_age_max_clamps_to_120(self, demo1_auth):
        r = requests.put(f"{BASE_URL}/api/me/filters",
                         json={"age_min": 25, "age_max": 999},
                         headers=demo1_auth["headers"], timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["filters"]["age_max"] == 120

    def test_distance_max_clamps_to_1(self, demo1_auth):
        r = requests.put(f"{BASE_URL}/api/me/filters",
                         json={"distance_max": -5},
                         headers=demo1_auth["headers"], timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["filters"]["distance_max"] == 1


# --------------------------------------------------------------------------- #
# 7. DELETE /api/me/filters                                                   #
# --------------------------------------------------------------------------- #
class TestDeleteFilters:
    def test_delete_unsets(self, demo1_auth, mongo):
        # save something first
        requests.put(f"{BASE_URL}/api/me/filters",
                     json={"age_min": 25, "age_max": 35},
                     headers=demo1_auth["headers"], timeout=15)
        d = requests.delete(f"{BASE_URL}/api/me/filters", headers=demo1_auth["headers"], timeout=15)
        assert d.status_code == 200
        assert d.json()["filters"] == {}
        g = requests.get(f"{BASE_URL}/api/me/filters", headers=demo1_auth["headers"], timeout=15)
        assert g.status_code == 200
        assert g.json()["filters"] == {}
        u = mongo.users.find_one({"id": demo1_auth["user_id"]}, {"_id": 0, "filters": 1})
        assert "filters" not in (u or {}) or not (u.get("filters"))


# --------------------------------------------------------------------------- #
# 8. /api/discover filter application                                         #
# --------------------------------------------------------------------------- #
class TestDiscoverFilters:
    def test_age_filter_excludes_out_of_range(self, demo1_auth):
        # Set narrow age range
        requests.put(f"{BASE_URL}/api/me/filters",
                     json={"age_min": 25, "age_max": 40},
                     headers=demo1_auth["headers"], timeout=15)
        r = requests.get(f"{BASE_URL}/api/discover", headers=demo1_auth["headers"], timeout=20)
        assert r.status_code == 200, r.text
        profiles = r.json().get("profiles", [])
        for p in profiles:
            age = p.get("age")
            assert age is None or 25 <= age <= 40, f"profile {p.get('id')} age={age} outside 25-40"

    def test_recently_active_only_filters_old_profiles(self, demo1_auth, mongo):
        # Apply recently_active_only=true
        requests.put(f"{BASE_URL}/api/me/filters",
                     json={"recently_active_only": True},
                     headers=demo1_auth["headers"], timeout=15)
        r = requests.get(f"{BASE_URL}/api/discover", headers=demo1_auth["headers"], timeout=20)
        assert r.status_code == 200, r.text
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        for p in r.json().get("profiles", []):
            la = p.get("last_active")
            if la:
                try:
                    ts = datetime.fromisoformat(la.replace("Z", "+00:00"))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    assert ts >= cutoff, f"profile {p.get('id')} last_active={la} older than 24h cutoff"
                except (ValueError, TypeError):
                    pass

    def test_premium_education_filter(self, premium_auth, mongo, demo2_auth):
        # Seed demo2 with education=bachelor in DB
        mongo.users.update_one({"id": demo2_auth["user_id"]}, {"$set": {"education": "bachelor"}})
        try:
            # set premium filter to education=['bachelor']
            r = requests.put(f"{BASE_URL}/api/me/filters",
                             json={"education": ["bachelor"]},
                             headers=premium_auth["headers"], timeout=15)
            assert r.status_code == 200, r.text
            d = requests.get(f"{BASE_URL}/api/discover", headers=premium_auth["headers"], timeout=20)
            assert d.status_code == 200, d.text
            for p in d.json().get("profiles", []):
                assert p.get("education") == "bachelor", f"profile {p.get('id')} education={p.get('education')}"
        finally:
            requests.delete(f"{BASE_URL}/api/me/filters", headers=premium_auth["headers"], timeout=15)
