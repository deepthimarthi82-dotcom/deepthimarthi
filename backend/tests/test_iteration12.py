"""Iteration 12 tests:
- Tighter filter clamps: age 18-99, height 140-220cm, distance 1-500
- Swipe counter ∞ display (backend returns 999999 for VIP)
- Top-bar city selector backend: PUT /api/me/location with geocoding
- Regression: existing routes still work end-to-end
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://spark-dating-118.preview.emergentagent.com").rstrip("/")

VIP = {"email": "deepthimarthi82@gmail.com", "password": "Spark2026!"}
DEMO1 = {"email": "demo1@spark.app", "password": "password123"}


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Login failed for {creds['email']}: {r.status_code} {r.text[:200]}")
    return r.json()


@pytest.fixture(scope="module")
def vip_headers():
    data = _login(VIP)
    return {"Authorization": f"Bearer {data['token']}"}, data["user_id"]


@pytest.fixture(scope="module")
def demo1_headers():
    data = _login(DEMO1)
    return {"Authorization": f"Bearer {data['token']}"}, data["user_id"]


# ========== FILTER CLAMP TESTS ==========

class TestFilterClamps:
    """Verify PUT /api/me/filters clamps to new tighter ranges."""

    def test_age_max_clamps_to_99(self, vip_headers):
        h, _ = vip_headers
        r = requests.put(f"{BASE_URL}/api/me/filters", json={"age_max": 120}, headers=h, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["filters"]["age_max"] == 99

    def test_age_min_clamps_to_18(self, vip_headers):
        h, _ = vip_headers
        r = requests.put(f"{BASE_URL}/api/me/filters", json={"age_min": 10}, headers=h, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["filters"]["age_min"] == 18

    def test_age_min_above_99_clamps_to_99(self, vip_headers):
        h, _ = vip_headers
        # age_min=100 alone: clamped to 99 (max). Sending without age_max so no 400.
        r = requests.put(f"{BASE_URL}/api/me/filters", json={"age_min": 100}, headers=h, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["filters"]["age_min"] == 99

    def test_age_max_below_18_clamps_to_18(self, vip_headers):
        h, _ = vip_headers
        r = requests.put(f"{BASE_URL}/api/me/filters", json={"age_max": 15}, headers=h, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["filters"]["age_max"] == 18

    def test_height_min_clamps_to_140(self, vip_headers):
        h, _ = vip_headers
        r = requests.put(f"{BASE_URL}/api/me/filters", json={"height_cm_min": 100}, headers=h, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["filters"]["height_cm_min"] == 140

    def test_height_max_clamps_to_220(self, vip_headers):
        h, _ = vip_headers
        r = requests.put(f"{BASE_URL}/api/me/filters", json={"height_cm_max": 250}, headers=h, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["filters"]["height_cm_max"] == 220

    def test_distance_max_clamps_to_500(self, vip_headers):
        h, _ = vip_headers
        r = requests.put(f"{BASE_URL}/api/me/filters", json={"distance_max": 2000}, headers=h, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["filters"]["distance_max"] == 500

    def test_cleanup_filters(self, vip_headers):
        h, _ = vip_headers
        r = requests.delete(f"{BASE_URL}/api/me/filters", headers=h, timeout=30)
        assert r.status_code == 200


# ========== SWIPES REMAINING (VIP gets 999999) ==========

class TestSwipesRemaining:
    def test_vip_has_999999_swipes(self, vip_headers):
        h, _ = vip_headers
        r = requests.get(f"{BASE_URL}/api/discover", headers=h, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "swipes_remaining" in data
        assert data["swipes_remaining"] == 999999, f"Expected 999999, got {data['swipes_remaining']}"
        assert data["super_likes_remaining"] == 999999, f"Expected 999999 super, got {data['super_likes_remaining']}"

    def test_free_user_has_finite_swipes(self, demo1_headers):
        h, _ = demo1_headers
        r = requests.get(f"{BASE_URL}/api/discover", headers=h, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # Free user has 20 likes/day per credentials doc, but anything < 999999 is fine
        assert data["swipes_remaining"] < 999999
        assert isinstance(data["swipes_remaining"], int)


# ========== LOCATION ENDPOINT ==========

class TestLocationEndpoint:
    """PUT /api/me/location — geocoding + persistence."""

    def test_location_with_city_and_country(self, demo1_headers):
        h, _ = demo1_headers
        r = requests.put(
            f"{BASE_URL}/api/me/location",
            json={"city": "San Francisco", "country": "USA"},
            headers=h,
            timeout=60,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["location"] == "San Francisco"
        assert data["country"] == "USA"
        assert data["geocoded"] is True
        # SF roughly 37.78, -122.4
        assert data["latitude"] is not None
        assert data["longitude"] is not None
        assert 36 < data["latitude"] < 39, f"Expected lat ~37.78, got {data['latitude']}"
        assert -124 < data["longitude"] < -121, f"Expected lng ~-122.4, got {data['longitude']}"

    def test_get_me_reflects_updated_location(self, demo1_headers):
        h, _ = demo1_headers
        # Set first
        requests.put(
            f"{BASE_URL}/api/me/location",
            json={"city": "San Francisco", "country": "USA"},
            headers=h, timeout=60,
        )
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=h, timeout=30)
        assert r.status_code == 200, r.text
        user = r.json()
        assert user.get("location") == "San Francisco"

    def test_empty_city_returns_400(self, demo1_headers):
        h, _ = demo1_headers
        r = requests.put(f"{BASE_URL}/api/me/location", json={"city": ""}, headers=h, timeout=30)
        assert r.status_code == 400, r.text

    def test_whitespace_only_city_returns_400(self, demo1_headers):
        h, _ = demo1_headers
        r = requests.put(f"{BASE_URL}/api/me/location", json={"city": "   "}, headers=h, timeout=30)
        assert r.status_code == 400, r.text

    def test_city_only_no_country_works(self, demo1_headers):
        h, _ = demo1_headers
        r = requests.put(f"{BASE_URL}/api/me/location", json={"city": "Paris"}, headers=h, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["location"] == "Paris"
        # geocoding should succeed for Paris
        assert data["geocoded"] is True
        assert data["latitude"] is not None


# ========== REGRESSION: Existing routes ==========

class TestRegression:
    def test_discover_works(self, demo1_headers):
        h, _ = demo1_headers
        r = requests.get(f"{BASE_URL}/api/discover", headers=h, timeout=30)
        assert r.status_code == 200
        assert "profiles" in r.json()

    def test_matches_works(self, demo1_headers):
        h, _ = demo1_headers
        r = requests.get(f"{BASE_URL}/api/matches", headers=h, timeout=30)
        assert r.status_code == 200

    def test_likes_works(self, demo1_headers):
        h, _ = demo1_headers
        r = requests.get(f"{BASE_URL}/api/likes-you", headers=h, timeout=30)
        # Free user should still get response (possibly blurred). Accept 200/402.
        assert r.status_code in (200, 402)

    def test_profile_get(self, demo1_headers):
        h, _ = demo1_headers
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=h, timeout=30)
        assert r.status_code == 200
        u = r.json()
        assert u["email"] == DEMO1["email"]

    def test_filters_get(self, demo1_headers):
        h, _ = demo1_headers
        r = requests.get(f"{BASE_URL}/api/me/filters", headers=h, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "filters" in data
        assert "is_premium" in data
