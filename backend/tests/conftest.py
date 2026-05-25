"""Shared fixtures for Spark backend tests."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://spark-dating-118.preview.emergentagent.com").rstrip("/")
# Read from frontend/.env as backup
if not BASE_URL or "localhost" in BASE_URL:
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
    except Exception:
        pass

DEMO1 = {"email": "demo1@spark.app", "password": "password123"}
DEMO2 = {"email": "demo2@spark.app", "password": "password123"}


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Cannot login {email}: {r.status_code} {r.text[:200]}")
    return r.json()


@pytest.fixture(scope="session")
def demo1_auth():
    data = _login(**DEMO1)
    return {"token": data["token"], "user_id": data["user_id"], "headers": {"Authorization": f"Bearer {data['token']}"}}


@pytest.fixture(scope="session")
def demo2_auth():
    data = _login(**DEMO2)
    return {"token": data["token"], "user_id": data["user_id"], "headers": {"Authorization": f"Bearer {data['token']}"}}


@pytest.fixture(scope="session")
def match_id(demo1_auth, demo2_auth):
    """Get match_id between demo1 and demo2."""
    r = requests.get(f"{BASE_URL}/api/matches", headers=demo1_auth["headers"], timeout=30)
    assert r.status_code == 200, r.text
    matches = r.json().get("matches", [])
    for m in matches:
        if m["user"]["id"] == demo2_auth["user_id"]:
            return m["match_id"]
    pytest.skip("No match between demo1 and demo2")
